"""Tiếp nhận tài liệu học thuật (PDF, DOCX, PPTX) — điểm vào của pipeline RAG.

Đây là nơi đưa tài liệu (ví dụ: PlanPJAI.docx, giáo trình, slide...) vào hệ
thống. Sau khi upload, worker nền (task_process_document) sẽ:
  1. Lưu file gốc vào MinIO
  2. Trích xuất text (rag/ingestion.py)
  3. Phân mảnh ngữ nghĩa (rag/chunking.py)
  4. Vector hóa + lưu vào Qdrant (rag/vector_store.py)
Chỉ sau bước 4, tài liệu mới thực sự có thể được Agent truy hồi (RAG).
"""
import io
import mimetypes
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.config import settings
from app.core.database import minio_client
from app.models.models import Document, User
from app.worker.tasks import task_process_document

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx"}
# Chặn file quá lớn ở tầng API để tránh làm nghẽn worker/GPU phía sau.
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename = file.filename or ""
    if not filename.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu tên file.")

    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Định dạng '{extension or 'không xác định'}' không được hỗ trợ. "
            f"Chỉ nhận: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    mime_type = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File rỗng.")
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File vượt quá giới hạn {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    document = Document(
        owner_id=current_user.id,
        filename=filename,
        mime_type=mime_type,
        status="pending",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    storage_path = f"{document.id}{extension}"

    try:
        if not minio_client.bucket_exists(settings.minio_bucket):
            minio_client.make_bucket(settings.minio_bucket)

        minio_client.put_object(
            settings.minio_bucket,
            storage_path,
            io.BytesIO(contents),
            length=len(contents),
            content_type=mime_type,
        )
    except Exception as exc:
        document.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Không thể lưu file vào kho lưu trữ: {exc}",
        ) from exc

    document.storage_path = storage_path
    await db.commit()

    task_process_document.delay(str(document.id), storage_path, mime_type)

    return {"document_id": str(document.id), "status": document.status}


@router.get("/{document_id}/status")
async def get_document_status(document_id: str, db: AsyncSession = Depends(get_db)):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="document_id không hợp lệ."
        ) from exc

    result = await db.execute(select(Document).where(Document.id == doc_uuid))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài liệu.")

    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "status": document.status,
    }
