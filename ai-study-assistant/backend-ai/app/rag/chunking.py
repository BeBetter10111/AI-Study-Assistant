import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(text: str, max_tokens: int = 512, overlap: int = 50) -> list[str]:
    """Cắt văn bản ngữ nghĩa (Semantic Chunking).

    Phân mảnh văn bản theo ranh giới ngữ nghĩa (đoạn/câu), không cắt cứng
    theo ký tự, để mỗi chunk giữ trọn vẹn ý nghĩa trước khi vector hóa.
    """
    if not text or not text.strip():
        logging.warning("chunk_text nhận văn bản rỗng, trả về danh sách chunk rỗng.")
        return []

    try:
        # Sử dụng tokenizer cl100k_base (chuẩn của OpenAI) để đếm chính xác số lượng token
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=max_tokens,
            chunk_overlap=overlap,
            # Thứ tự ưu tiên cắt: Hết đoạn -> Hết dòng -> Hết câu -> Dấu cách -> Từng ký tự
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = text_splitter.split_text(text)
        
        # Lọc bỏ các chunk quá ngắn (có thể do nhiễu khoảng trắng hoặc lỗi format tài liệu)
        valid_chunks = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 15]
        
        return valid_chunks
        
    except Exception as e:
        logging.error(f"Lỗi hệ thống khi chunking văn bản: {str(e)}")
        # Fallback an toàn: Cắt cứng theo số lượng ký tự trung bình (1 token ~ 4 ký tự) 
        # để đảm bảo pipeline không bị sập nếu thư viện đếm token gặp sự cố
        char_chunk_size = max(max_tokens * 4, 1)
        char_overlap = min(overlap * 4, char_chunk_size - 1) if char_chunk_size > 1 else 0
        step = max(char_chunk_size - char_overlap, 1)
        return [text[i:i + char_chunk_size] for i in range(0, len(text), step)]