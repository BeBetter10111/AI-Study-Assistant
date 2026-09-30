# Tìm data cho RAG — nguồn đề xuất & bao nhiêu là đủ

## 1) Ưu tiên nguồn theo thứ tự này

1. **Tài liệu môn học của chính bạn** (slide bài giảng, giáo trình được
   phát, lab handout, đề cương IT159IU/IT090IU/IT069IU/IT079IU/IT089IU) —
   đây LUÔN là nguồn tốt nhất cho một trợ lý học tập cá nhân: khớp 100%
   với những gì bạn sẽ bị hỏi/thi, và bạn có sẵn quyền sử dụng (không vướng
   bản quyền vì chỉ dùng cá nhân, không public lại). Đừng bỏ qua nguồn này
   để đi tìm data ngoài — nó vẫn nên là phần lõi của corpus.
2. **Tài liệu mở (open-licensed)** để bổ sung phần môn học bạn chưa có
   slide đầy đủ, hoặc muốn có định nghĩa/ví dụ chuẩn hơn để đối chiếu.
3. **Sách giáo trình có bản quyền** (AIMA của Russell & Norvig, CLRS,
   Silberschatz Database System Concepts...) — dùng để ĐỌC/tham khảo bình
   thường thì không sao, nhưng KHÔNG nên bulk-scrape/OCR rồi nhét toàn bộ
   nội dung vào Qdrant nếu công cụ này sẽ được chia sẻ ngoài phạm vi cá
   nhân (kể cả public trên GitHub) — vi phạm bản quyền rõ ràng. Dùng cá
   nhân, không phân phối lại, rủi ro thấp hơn nhiều nhưng vẫn nên ưu tiên
   nguồn open trước.

## 2) Nguồn mở cụ thể, khớp với từng môn trong coursework của bạn

| Môn (coursework.md) | Nguồn đề xuất | Giấy phép |
|---|---|---|
| AI (IT159IU) — search, CSP, agents | [MIT OCW 6.034 — Artificial Intelligence](https://ocw.mit.edu/courses/6-034-artificial-intelligence-spring-2005/pages/lecture-notes/) — lecture notes PDF đúng thứ tự: Search → CSP/Games → Learning → Logic | CC BY-NC-SA (dùng học tập cá nhân OK) |
| DSA — BST, hash table, DFS, Dijkstra, SCC | [Open Data Structures](https://opendatastructures.org/) (Pat Morin) — có bản Java/C++/Python/pseudocode | CC BY 2.5 — tự do dùng, kể cả thương mại, chỉ cần ghi nguồn |
| Database (IT079IU) — ER, normalization, SQL | [Database Design – 2nd Edition](https://opentextbc.ca/dbdesign01/) (Watt & Eng, BCcampus) | CC BY 4.0 |
| OOAD/OOP (IT090IU, IT069IU) — UML, design patterns, SOLID | [Refactoring.Guru — Design Patterns](https://refactoring.guru/design-patterns) (đọc/tóm tắt thủ công từng pattern, không bulk-scrape vì đây không phải nội dung mở) + slide OOAD/OOP của trường bạn | Nội dung riêng — chỉ nên tự ghi chú lại, không crawl toàn site |
| Computer Architecture (IT089IU) — MIPS pipeline | [nand2tetris](https://www.nand2tetris.org/) phần Chapter 4-5 (miễn phí, không cần mua sách) + slide MIPS/QtSpim của trường | Miễn phí cho mục đích học tập |
| Principles of Programming Languages | [MIT OCW 6.820 hoặc Stanford CS242 lecture notes](https://ocw.mit.edu/search/?q=programming%20languages) | CC BY-NC-SA |

Với các môn chưa có sẵn tài liệu mở khớp 100% ngôn ngữ Vietnamese, cách
thực dụng nhất là: dùng slide tiếng Việt của trường làm phần lõi, dùng
nguồn tiếng Anh ở trên làm phần bổ sung/đối chiếu khi cần giải thích sâu
hơn — pipeline RAG của bạn không yêu cầu toàn bộ corpus cùng 1 ngôn ngữ,
vì câu hỏi tiếng Việt vẫn có thể retrieve trúng đoạn tiếng Anh nếu
embedding model đa ngôn ngữ (sentence-transformers/all-MiniLM-L6-v2 hiện
đang dùng trong `vector_store.py` là mô hình chủ yếu tiếng Anh — nếu phần
lớn câu hỏi của bạn bằng tiếng Việt, cân nhắc đổi sang một multilingual
model như `intfloat/multilingual-e5-base` để retrieval chính xác hơn).

## 3) Bao nhiêu data là đủ? — tính theo đúng cấu hình chunking hiện tại

`chunk_text()` trong `backend-ai/app/rag/chunking.py` đang cắt theo
**512 token/chunk, overlap 50 token** → mỗi chunk hữu ích ~462 token mới.
Với văn bản tiếng Anh, 512 token ≈ 380–400 từ (~1.3 trang A4 chữ thường).
Với tiếng Việt có dấu, tokenizer cl100k_base thường tốn nhiều token hơn
mỗi từ (khoảng 1.3–1.8×), nên 512 token ≈ 220–290 từ tiếng Việt (~0.8 trang).

Quy đổi thực tế:

| Mục tiêu | Số trang tài liệu gốc | Số chunk (~) |
|---|---|---|
| MVP — đủ để demo pipeline chạy đúng, trả lời được câu hỏi cơ bản 1 môn | 30–50 trang (2–3 chương/1 bộ slide) | 40–80 chunk |
| Dùng thật để ôn 1 môn cho kỳ thi | 150–250 trang (cả giáo trình môn đó) | 250–450 chunk |
| Phủ cả 5-6 môn trong coursework của bạn | 800–1,500 trang tổng | 1,500–3,000 chunk |

**Xác nhận: với quy mô đồ án cá nhân này, bạn KHÔNG cần nhiều data như các
RAG production (không cần hàng chục nghìn chunk).** Lý do:
- Đây là trợ lý học tập cho **chính bạn**, phạm vi câu hỏi giới hạn trong
  vài môn học cụ thể — không phải một trợ lý tổng quát phải trả lời mọi
  chủ đề.
- Retrieval chất lượng (top_k=4 trong `chat.py` hiện tại) quan trọng hơn
  số lượng — 80 chunk chất lượng cao (đúng nội dung, không nhiễu) trả lời
  tốt hơn 2,000 chunk chứa nhiều nội dung không liên quan.
- Bắt đầu với **1 môn học đầy đủ** (ví dụ Database — vì đã có bản BCcampus
  CC-BY sẵn, dễ tải nhất) để kiểm tra toàn bộ pipeline (upload → chunk →
  embed → hỏi đáp → quiz) chạy đúng, rồi mới mở rộng dần sang các môn
  khác — đỡ tốn công ingest lại nếu phát hiện chunk_size/overlap chưa hợp
  lý cho loại nội dung của bạn (ví dụ slide có nhiều bullet ngắn thường
  cần chunk nhỏ hơn 512 token).

## 4) Việc cần làm tiếp (gợi ý, chưa triển khai)

- Viết 1 script nhỏ (`scripts/seed_documents.py`?) gọi thẳng
  `POST /api/documents/upload` cho từng file PDF trong một thư mục, để
  nạp hàng loạt thay vì upload tay từng file qua UI — hữu ích khi bạn đã
  gom đủ 30-50 trang đầu tiên và muốn nạp nhanh.
- Cân nhắc đổi embedding model sang multilingual nếu phần lớn câu hỏi
  bằng tiếng Việt (xem mục 2).
