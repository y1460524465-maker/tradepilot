"""文件上传与解析 HTTP 接口（TRD 6.2 / 第十三章）。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.file import (
    FileDetail,
    FileList,
    FileParseResult,
    FileRead,
    ParseSummary,
)
from app.services.file_service import FileService

router = APIRouter(tags=["files"])


@router.post(
    "/tasks/{task_id}/files",
    response_model=FileList,
    status_code=status.HTTP_201_CREATED,
)
def upload_files(
    task_id: uuid.UUID,
    files: list[UploadFile],
    db: Session = Depends(get_db),
) -> FileList:
    saved = FileService(db).save_uploads(task_id, files)
    return FileList(total=len(saved), items=saved)


@router.get("/tasks/{task_id}/files", response_model=FileList)
def list_files(task_id: uuid.UUID, db: Session = Depends(get_db)) -> FileList:
    files, total = FileService(db).list_files(task_id)
    return FileList(total=total, items=files)


@router.get("/tasks/{task_id}/files/{file_id}", response_model=FileDetail)
def get_file(task_id: uuid.UUID, file_id: uuid.UUID, db: Session = Depends(get_db)) -> FileDetail:
    return FileDetail.model_validate(FileService(db).get_file(task_id, file_id))


@router.get("/tasks/{task_id}/files/{file_id}/download")
def download_file(
    task_id: uuid.UUID, file_id: uuid.UUID, db: Session = Depends(get_db)
) -> FileResponse:
    """下载原始文件。先校验文件归属任务，再校验磁盘路径（TRD 6.3：下载前校验访问权限）。"""
    file = FileService(db).get_file(task_id, file_id)
    path = Path(file.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件已丢失")
    return FileResponse(path, filename=file.original_filename)


@router.post("/tasks/{task_id}/parse", response_model=ParseSummary)
def parse_files(task_id: uuid.UUID, db: Session = Depends(get_db)) -> ParseSummary:
    parsed = FileService(db).parse_task_files(task_id)
    return ParseSummary(
        task_id=task_id,
        results=[
            FileParseResult(
                file_id=f.id,
                filename=f.original_filename,
                status=f.status,
                row_count=(f.parsed_preview or {}).get("total_rows"),
                error=f.error_message,
            )
            for f in parsed
        ],
    )
