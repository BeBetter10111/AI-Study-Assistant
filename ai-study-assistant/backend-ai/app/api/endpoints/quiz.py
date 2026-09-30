"""Đánh giá tự động — sinh quiz bằng Tool Calling, chấm điểm và cập nhật RL."""
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.llm_engine import llm_engine
from app.models.models import QuizAttempt, User
from app.rag.vector_store import vector_store
from app.rl import agent as rl_agent

logger = logging.getLogger(__name__)
router = APIRouter()


class QuizQuestion(BaseModel):
    question: str
    options: List[str] = Field(min_length=2, max_length=8)
    correct_index: int
    explanation: str


class QuizSchema(BaseModel):
    topic: str
    questions: List[QuizQuestion]


class GenerateQuizRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    num_questions: int = Field(default=10, ge=1, le=50)
    document_id: Optional[str] = None


class GenerateQuizResponse(BaseModel):
    quiz_id: str
    topic: str
    questions: List[QuizQuestion]


class SubmitQuizRequest(BaseModel):
    # Không nhận user_id từ client: current_user lấy từ JWT để tránh việc
    # người dùng tự khai user_id của người khác khi nộp bài (edge case bảo mật).
    document_id: Optional[str] = None
    is_correct: bool
    response_time_s: float = Field(ge=0)
    hints_used: int = Field(default=0, ge=0)


@router.post("/generate", response_model=GenerateQuizResponse)
async def generate_quiz(payload: GenerateQuizRequest):
    hits = vector_store.search_similar_chunks(
        query=payload.topic, limit=8, document_id=payload.document_id
    )
    if not hits:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy ngữ cảnh phù hợp cho chủ đề này. "
            "Vui lòng tải lên tài liệu liên quan trước khi tạo quiz.",
        )

    context = "\n\n".join(hit["content"] for hit in hits)
    prompt = (
        f"Dựa trên ngữ cảnh sau đây, hãy tạo {payload.num_questions} câu hỏi trắc nghiệm "
        f"về chủ đề '{payload.topic}'. Mỗi câu có tối thiểu 2 lựa chọn, chỉ 1 đáp án đúng "
        f"(correct_index là chỉ số 0-based trong mảng options), kèm lời giải thích ngắn gọn.\n\n"
        f"Ngữ cảnh:\n{context}"
    )

    try:
        result = llm_engine.generate_structured_output(prompt=prompt, schema_class=QuizSchema)
    except Exception as exc:
        logger.error(f"Lỗi khi sinh quiz: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể sinh bộ câu hỏi từ mô hình ngôn ngữ.",
        ) from exc

    questions = result.get("questions") or []
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Mô hình không trả về câu hỏi hợp lệ."
        )

    # Double-check biên: loại bỏ câu hỏi có correct_index nằm ngoài mảng options
    # (mô hình ngôn ngữ đôi khi sinh chỉ số sai) để tránh lỗi khi chấm điểm.
    valid_questions = [
        q for q in questions if 0 <= q.get("correct_index", -1) < len(q.get("options", []))
    ]
    if not valid_questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Mô hình trả về câu hỏi không hợp lệ (correct_index sai).",
        )

    return GenerateQuizResponse(
        quiz_id=str(uuid.uuid4()),
        topic=result.get("topic", payload.topic),
        questions=valid_questions,
    )


@router.post("/{quiz_id}/submit")
async def submit_quiz_result(
    quiz_id: str,
    payload: SubmitQuizRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        quiz_uuid = uuid.UUID(quiz_id)
        document_uuid = uuid.UUID(payload.document_id) if payload.document_id else None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quiz_id hoặc document_id không hợp lệ.",
        ) from exc

    attempt = QuizAttempt(
        user_id=current_user.id,
        document_id=document_uuid,
        quiz_id=quiz_uuid,
        is_correct=payload.is_correct,
        response_time_s=payload.response_time_s,
        hints_used=payload.hints_used,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    next_difficulty = rl_agent.update_state(
        user_id=str(current_user.id),
        quiz_result={
            "is_correct": payload.is_correct,
            "response_time_s": payload.response_time_s,
            "hints_used": payload.hints_used,
        },
    )

    return {"attempt_id": str(attempt.id), "next_difficulty": next_difficulty}
