# AI Study Assistant

Trợ lý học tập thông minh — RAG-based Q&A, tự động tạo quiz/flashcard, và
cá nhân hóa lộ trình học bằng Reinforcement Learning.

## Kiến trúc

- **frontend/** — ReactJS (Tailwind CSS)
- **backend-ai/** — FastAPI + AI Engine (RAG, RL) + Celery worker
- **postgres** — dữ liệu quan hệ (users, quiz, lịch sử làm bài)
- **qdrant** — vector store cho RAG
- **minio** — lưu trữ file tài liệu gốc
- **redis + celery** — xử lý bất đồng bộ (ingest tài liệu, chấm điểm nền)

## Chạy dự án

```bash
cp .env .env.local   # chỉnh sửa giá trị thật
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- Qdrant dashboard: http://localhost:6333/dashboard
- MinIO console: http://localhost:9001

## Ràng buộc chính

- Thời gian phản hồi mỗi truy vấn ≤ 800ms
- Không dùng web search tự do (chống hallucination — Grounded RAG only)
- Suy luận LLM phân tán trên 4 lõi GPU NVIDIA A16 độc lập, không tràn VRAM
- Toàn bộ kiến trúc đóng gói bằng Docker
