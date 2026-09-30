"""Hàm chạy ngầm — pipeline biến 1 file tài liệu thành dữ liệu RAG."""
import logging
import os
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import minio_client
from app.models.models import Document
from app.rag import chunking, ingestion
from app.rag.vector_store import vector_store
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

# Celery worker chạy đồng bộ (không async), nên dùng một engine SQLAlchemy
# đồng bộ riêng (bỏ driver asyncpg) thay vì tái sử dụng async_session của API.
# Khởi tạo LAZY (chỉ tạo khi task đầu tiên thực sự chạy) thay vì ngay lúc
# import module: import-time side effect từng khiến cả worker crash ngay
# khi khởi động nếu thiếu driver đồng bộ (psycopg2) — driver này đã được
# bổ sung vào requirements.txt, nhưng lazy-init vẫn an toàn hơn vì không
# ép mọi import app.worker.tasks (kể cả từ test) phải có driver DB sẵn sàng.
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.database_url.replace("+asyncpg", ""))
    return _sync_engine


def _update_document_status(document_id: str, status: str) -> None:
    with Session(_get_sync_engine()) as session:
        document = session.get(Document, document_id)
        if document is None:
            logger.warning(f"Không tìm thấy Document {document_id} để cập nhật status.")
            return
        document.status = status
        session.commit()


@celery_app.task(name="task_process_document", bind=True, max_retries=3)
def task_process_document(self, document_id: str, storage_path: str, mime_type: str):
    """Đây là nơi tài liệu thực sự "được nạp vào RAG":

    1. Tải file gốc từ MinIO về ổ đĩa tạm (documents.py chỉ lưu storage_path,
       không phải đường dẫn cục bộ, nên phải tải về trước khi đọc)
    2. ingestion.extract_text()   — đọc PDF/DOCX/PPTX ra text
    3. chunking.chunk_text()      — phân mảnh ngữ nghĩa
    4. vector_store.upsert_chunks() — embed từng chunk và lưu vào Qdrant

    Chỉ sau khi task này chạy xong (status="embedded"), Agent mới
    "biết" nội dung tài liệu khi trả lời câu hỏi.
    """
    _update_document_status(document_id, "chunking")

    suffix = os.path.splitext(storage_path)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = tmp_file.name

        minio_client.fget_object(settings.minio_bucket, storage_path, tmp_path)

        text = ingestion.extract_text(tmp_path, mime_type)
        if not text.strip():
            raise ValueError("Không trích xuất được nội dung văn bản nào từ tài liệu.")

        chunks = chunking.chunk_text(text)
        if not chunks:
            raise ValueError("Tài liệu không tạo ra chunk hợp lệ nào sau khi phân mảnh.")

        vector_store.upsert_chunks(chunks, document_id)
        _update_document_status(document_id, "embedded")
        logger.info(f"Đã xử lý xong tài liệu {document_id}: {len(chunks)} chunks.")

    except Exception as exc:
        logger.error(f"Lỗi khi xử lý tài liệu {document_id}: {exc}")
        _update_document_status(document_id, "failed")
        raise
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
