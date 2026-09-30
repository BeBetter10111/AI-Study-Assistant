"""Entry point FastAPI — Routing, WebSocket."""
from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.api.endpoints import auth, chat, documents, quiz

app = FastAPI(title="AI Study Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: siết lại theo domain frontend thật
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["quiz"])


@app.get("/health")
async def health(response: Response, db: AsyncSession = Depends(get_db)):
    """Readiness check thật, không chỉ "process còn sống".

    CD pipeline (và docker-compose healthcheck) dựa vào endpoint này để
    quyết định container đã sẵn sàng nhận traffic hay chưa — nếu chỉ trả
    200 vô điều kiện, một backend "sống" nhưng chưa kết nối được Postgres
    vẫn bị coi là "khỏe", làm mọi request đầu tiên fail.
    """
    checks = {"database": "ok"}
    is_healthy = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — health check không nên crash vì bất kỳ lỗi driver nào
        checks["database"] = f"unreachable: {exc}"
        is_healthy = False

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if is_healthy else "degraded", "checks": checks}
