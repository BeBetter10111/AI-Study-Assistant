"""Chatbot RAG — phân loại ý định, hybrid search, sinh câu trả lời kèm nguồn."""
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.core.llm_engine import llm_engine
from app.rag.vector_store import vector_store

logger = logging.getLogger(__name__)
router = APIRouter()

QUIZ_KEYWORDS = ("quiz", "trắc nghiệm", "câu hỏi ôn tập", "làm bài kiểm tra")
SUMMARY_KEYWORDS = ("tóm tắt", "summary", "summarize")


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_id: Optional[str] = None
    top_k: int = Field(default=4, ge=1, le=20)


class Citation(BaseModel):
    document_id: str
    chunk_index: int
    score: float
    content: str


class QueryResponse(BaseModel):
    intent: str
    answer: str
    citations: List[Citation]
    latency_ms: float


def _classify_intent(question: str) -> str:
    """Bộ định tuyến tác tử: phân loại 3 luồng chính — hỏi đáp, tạo quiz, tóm tắt.

    Dùng heuristic từ khóa làm fallback nhẹ, không tốn thêm 1 lượt gọi LLM,
    để không đội thêm độ trễ vào ngân sách 800ms/truy vấn.
    """
    lowered = question.lower()
    if any(keyword in lowered for keyword in QUIZ_KEYWORDS):
        return "quiz_generation"
    if any(keyword in lowered for keyword in SUMMARY_KEYWORDS):
        return "summarization"
    return "qa"


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Câu hỏi không được để trống.")

    start_time = time.perf_counter()
    intent = _classify_intent(question)

    # Luồng tạo quiz có endpoint riêng (chuyên sâu hơn, dùng Tool Calling) —
    # ở đây chỉ định tuyến ý định để chatbot phản hồi đúng hướng dẫn người
    # dùng, chưa gọi thẳng sang generate_quiz để tránh trộn 2 hợp đồng response.
    if intent == "quiz_generation":
        latency_ms = (time.perf_counter() - start_time) * 1000
        return QueryResponse(
            intent=intent,
            answer="Để tạo bộ câu hỏi trắc nghiệm, vui lòng dùng chức năng 'Tạo Quiz' "
            "và chọn chủ đề bạn muốn ôn tập.",
            citations=[],
            latency_ms=latency_ms,
        )

    hits = vector_store.search_similar_chunks(
        query=question,
        limit=payload.top_k,
        document_id=payload.document_id,
    )

    if not hits:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return QueryResponse(
            intent=intent,
            answer="Không tìm thấy nội dung liên quan trong tài liệu đã nạp. "
            "Vui lòng tải lên tài liệu học tập trước khi đặt câu hỏi.",
            citations=[],
            latency_ms=latency_ms,
        )

    context = "\n\n".join(f"[{i + 1}] {hit['content']}" for i, hit in enumerate(hits))

    if intent == "summarization":
        system_prompt = (
            "Bạn là trợ lý học tập. Hãy tóm tắt ngắn gọn, chính xác nội dung trong "
            "NGỮ CẢNH được cung cấp. Không thêm thông tin ngoài ngữ cảnh."
        )
    else:
        system_prompt = (
            "Bạn là trợ lý học tập chỉ được trả lời dựa trên NGỮ CẢNH được cung cấp. "
            "Nếu ngữ cảnh không đủ để trả lời, hãy nói rõ là không tìm thấy thông tin. "
            "Không được suy diễn hoặc dùng kiến thức bên ngoài ngữ cảnh (chống ảo giác)."
        )

    prompt = f"Ngữ cảnh:\n{context}\n\nCâu hỏi: {question}"
    answer = llm_engine.generate_rag_response(prompt=prompt, system_prompt=system_prompt)

    latency_ms = (time.perf_counter() - start_time) * 1000
    if latency_ms > settings.max_response_latency_ms:
        logger.warning(
            f"Truy vấn vượt ngưỡng độ trễ: {latency_ms:.0f}ms > {settings.max_response_latency_ms}ms"
        )

    citations = [
        Citation(
            document_id=hit["document_id"],
            chunk_index=hit["chunk_index"],
            score=hit["score"],
            content=hit["content"],
        )
        for hit in hits
    ]

    return QueryResponse(intent=intent, answer=answer, citations=citations, latency_ms=latency_ms)
