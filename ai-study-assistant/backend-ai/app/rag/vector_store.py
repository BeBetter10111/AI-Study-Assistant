import logging
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStoreManager:
    def __init__(self, collection_name: Optional[str] = None):
        # Trước đây dùng getattr(settings, "QDRANT_URL", ...) — sai tên field
        # (Settings dùng chữ thường: qdrant_url), nên luôn rơi vào giá trị mặc định
        # "http://localhost:6333" thay vì cấu hình thật trong docker-compose.
        self.collection_name = collection_name or settings.qdrant_collection
        self._qdrant_url = settings.qdrant_url
        self.vector_size = 384

        # Kết nối Qdrant + tải embedding model được trì hoãn đến lần dùng đầu
        # tiên (lazy init), thay vì chạy ngay khi import module. Nếu không,
        # main.py sẽ crash lúc khởi động API mỗi khi Qdrant chưa kịp sẵn sàng
        # (depends_on trong docker-compose chỉ đảm bảo thứ tự start container,
        # không đảm bảo service đã healthy).
        self._client: Optional[QdrantClient] = None
        self._embedding_model: Optional[SentenceTransformer] = None
        self._collection_ready = False

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=self._qdrant_url)
        return self._client

    @property
    def embedding_model(self) -> SentenceTransformer:
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        return self._embedding_model

    def _ensure_collection(self) -> None:
        if self._collection_ready:
            return
        self.init_collection()
        self._collection_ready = True

    def init_collection(self):
        """Khởi tạo Collection trên Qdrant nếu chưa tồn tại."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info(f"Đã tạo mới Qdrant Collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant Collection '{self.collection_name}' đã tồn tại.")
        except Exception as e:
            logger.error(f"Lỗi khi khởi tạo Qdrant collection: {str(e)}")
            raise e

    def upsert_chunks(
        self,
        chunks: List[str],
        document_id: str,
        start_chunk_idx: int = 0,
    ) -> bool:
        """
        Nhúng (embed) mảng văn bản và lưu toàn bộ vectors + payload vào Qdrant.

        :param chunks: Danh sách chuỗi văn bản đã cắt từ chunking.py
        :param document_id: ID của file tài liệu (để lọc theo từng file)
        :param start_chunk_idx: Chỉ số bắt đầu (phục vụ đánh số thứ tự chunk)
        :return: True nếu lưu thành công
        """
        if not chunks:
            logger.warning("Danh sách chunks rỗng, bỏ qua upsert.")
            return False

        self._ensure_collection()

        try:
            embeddings = self.embedding_model.encode(chunks, show_progress_bar=False)

            points = []
            for idx, (chunk_text, vector) in enumerate(zip(chunks, embeddings)):
                # Qdrant point id phải là UUID hoặc số nguyên — dùng UUID5 tất
                # định từ document_id + chỉ số chunk để cùng một chunk luôn map
                # về cùng một point (idempotent khi worker chạy lại/retry).
                chunk_index = start_chunk_idx + idx
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{chunk_index}"))

                point = models.PointStruct(
                    id=point_id,
                    vector=vector.tolist(),
                    payload={
                        "document_id": str(document_id),
                        "chunk_index": chunk_index,
                        "content": chunk_text,
                    },
                )
                points.append(point)

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            logger.info(f"Đã lưu thành công {len(points)} vectors cho tài liệu {document_id}")
            return True

        except Exception as e:
            logger.error(f"Lỗi khi upsert vectors vào Qdrant: {str(e)}")
            raise e

    def search_similar_chunks(
        self, query: str, limit: int = 4, document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Truy vấn tìm kiếm các đoạn văn bản có ngữ nghĩa gần nhất với câu hỏi."""
        if not query or not query.strip():
            return []
        if limit < 1:
            limit = 1

        try:
            self._ensure_collection()
            query_vector = self.embedding_model.encode(query).tolist()

            query_filter = None
            if document_id:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    ]
                )

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
            )

            results = []
            for hit in search_result:
                results.append(
                    {
                        "score": hit.score,
                        "content": hit.payload.get("content", ""),
                        "document_id": hit.payload.get("document_id", ""),
                        "chunk_index": hit.payload.get("chunk_index", 0),
                    }
                )

            return results
        except Exception as e:
            logger.error(f"Lỗi khi truy vấn Qdrant: {str(e)}")
            return []


# Singleton instance dùng chung cho toàn bộ ứng dụng
vector_store = VectorStoreManager()
