"""文件上传、安全校验、存储与解析编排（TRD 6.2 / 6.3 / 6.4）。

安全规则（TRD 6.3）：
- 检查文件扩展名和实际文件类型（magic bytes）
- 限制文件大小与上传数量
- 使用系统生成的文件名保存，不使用用户文件名作为路径
- 解析失败时记录错误信息，不让整个任务失败
"""

import uuid
from pathlib import Path

import fastapi
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.uploaded_file import FileStatus, FileTypeEnum, UploadedFile
from app.parsers import registry
from app.services.task_service import TaskService

# 扩展名白名单（TRD 6.1：.xlsx、.csv、文本型 .pdf）
EXTENSION_MAP: dict[str, FileTypeEnum] = {
    ".xlsx": FileTypeEnum.XLSX,
    ".csv": FileTypeEnum.CSV,
    ".pdf": FileTypeEnum.PDF,
}


def detect_file_type(filename: str, head: bytes) -> FileTypeEnum:
    """按扩展名 + 实际文件内容双重校验，二者不一致则拒绝。"""
    ext = Path(filename).suffix.lower()
    file_type = EXTENSION_MAP.get(ext)
    if file_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型：{ext or '(无扩展名)'}，仅支持 .xlsx / .csv / .pdf",
        )
    if file_type is FileTypeEnum.XLSX and not head.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="文件内容不是有效的 Excel（.xlsx）格式")
    if file_type is FileTypeEnum.PDF and not head.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="文件内容不是有效的 PDF 格式")
    if file_type is FileTypeEnum.CSV and b"\x00" in head:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="文件包含二进制内容，不是有效的 CSV 文本")
    return file_type


class FileService:
    def __init__(self, db: Session):
        self.db = db
        self.tasks = TaskService(db)

    def _ensure_task(self, task_id: uuid.UUID) -> None:
        """任务不存在时抛 404。"""
        self.tasks.get_task(task_id)

    # ---------- 上传 ----------

    def save_uploads(self, task_id: uuid.UUID, files: list[fastapi.UploadFile]) -> list[UploadedFile]:
        self._ensure_task(task_id)

        existing, _ = self.list_files(task_id)
        if len(existing) + len(files) > settings.max_files_per_task:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单个任务最多上传 {settings.max_files_per_task} 个文件",
            )

        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        saved: list[UploadedFile] = []
        for upload in files:
            saved.append(self._save_one(task_id, upload, max_bytes))
        return saved

    def _save_one(self, task_id: uuid.UUID, upload: UploadFile, max_bytes: int) -> UploadedFile:
        filename = upload.filename or "unnamed"
        # 边读边校验大小，避免超限文件占满内存
        chunks: list[bytes] = []
        total = 0
        while chunk := upload.file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件 {filename} 超过单文件上限 {settings.max_upload_size_mb} MB",
                )
            chunks.append(chunk)
        content = b"".join(chunks)
        if total == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"文件 {filename} 为空")
        head = content[:8]

        file_type = detect_file_type(filename, head)

        # 系统生成文件名，杜绝路径遍历（TRD 6.3）
        task_dir = Path(settings.storage_dir) / "uploads" / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        storage_path = task_dir / f"{uuid.uuid4().hex}{Path(filename).suffix.lower()}"
        storage_path.write_bytes(content)

        record = UploadedFile(
            task_id=task_id,
            original_filename=filename[:255],
            storage_path=str(storage_path),
            file_type=file_type,
            file_size=total,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    # ---------- 查询 / 详情 / 下载 ----------

    def list_files(self, task_id: uuid.UUID) -> tuple[list[UploadedFile], int]:
        self._ensure_task(task_id)
        files = (
            self.db.query(UploadedFile)
            .filter(UploadedFile.task_id == task_id)
            .order_by(UploadedFile.created_at.asc())
            .all()
        )
        return files, len(files)

    def get_file(self, task_id: uuid.UUID, file_id: uuid.UUID) -> UploadedFile:
        file = self.db.get(UploadedFile, file_id)
        if file is None or file.task_id != task_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"文件 {file_id} 不存在于任务 {task_id}")
        return file

    # ---------- 解析 ----------

    def parse_task_files(self, task_id: uuid.UUID) -> list[UploadedFile]:
        """执行任务内所有未解析/失败的文件解析，逐文件记录结果（TRD 6.3：失败记录原因）。"""
        self._ensure_task(task_id)
        files = (
            self.db.query(UploadedFile)
            .filter(
                UploadedFile.task_id == task_id,
                UploadedFile.status.in_([FileStatus.UPLOADED, FileStatus.PARSE_FAILED]),
            )
            .all()
        )
        for file in files:
            self._parse_one(file)
        self.db.commit()
        return files

    def _parse_one(self, file: UploadedFile) -> None:
        try:
            raw = registry.parse_file(file.file_type, Path(file.storage_path))
            file.parsed_preview = raw.to_preview()
            file.status = FileStatus.PARSED
            file.error_message = None
        except Exception as e:  # noqa: BLE001 —— 任何解析异常都只标记该文件失败
            file.status = FileStatus.PARSE_FAILED
            file.error_message = str(e)[:2000]
