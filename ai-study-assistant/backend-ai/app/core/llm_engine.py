import logging
from json import JSONDecodeError
from typing import Any, Dict, Optional

import torch
from outlines import generate, models
from pydantic import BaseModel
from vllm import LLM, SamplingParams

from app.config import settings

logger = logging.getLogger(__name__)

class LLMEngineManager:
    """
    Quản lý mô hình LLM chính dựa trên vLLM engine.
    Hỗ trợ chạy phân tán trên 4 GPU NVIDIA A16 và ép cấu trúc đầu ra (Structured Output) 
    bằng Outlines cho tính năng Tool Calling (Quiz / Flashcard).
    """

    def __init__(self):
        # Trước đây dùng getattr(settings, "LLM_MODEL_NAME", ...) — Settings
        # định nghĩa field bằng chữ thường (llm_model_name) nên getattr với
        # tên viết hoa luôn miss và rơi về giá trị mặc định, bỏ qua hoàn toàn
        # cấu hình thật trong .env/docker-compose.
        self.model_name = (
            settings.llm_model_name
            if settings.llm_model_name and settings.llm_model_name != "change-me"
            else "Qwen/Qwen2.5-7B-Instruct"
        )

        # Số lượng GPU phân tán (NVIDIA A16 có 4 lõi GPU)
        self.tensor_parallel_size = settings.llm_tensor_parallel_size

        # Tỷ lệ giới hạn VRAM sử dụng (0.85 = 85% VRAM mỗi GPU để tránh OOM)
        self.gpu_memory_utilization = settings.gpu_memory_utilization

        self.llm: Optional[LLM] = None
        self.outlines_model = None

        # Khởi tạo mô hình
        self._init_engine()

    def _init_engine(self):
        """Khởi tạo vLLM Engine và Outlines Wrapper."""
        try:
            logger.info(f"Đang tải LLM Model '{self.model_name}' trên {self.tensor_parallel_size} GPU...")

            # Kiểm tra khả dụng của CUDA
            if not torch.cuda.is_available():
                logger.warning("CUDA không khả dụng! vLLM yêu cầu môi trường có GPU.")
                return

            # Khởi tạo vLLM
            self.llm = LLM(
                model=self.model_name,
                tensor_parallel_size=self.tensor_parallel_size,
                gpu_memory_utilization=self.gpu_memory_utilization,
                max_model_len=4096,  # Giới hạn context window cho RAG
                trust_remote_code=True
            )

            # Đóng gói vLLM với Outlines để ép kiểu dữ liệu Structured Output
            self.outlines_model = models.vllm(self.llm)
            logger.info("Đã khởi tạo vLLM Engine thành công!")

        except Exception as e:
            logger.error(f"Lỗi khi khởi tạo vLLM Engine: {str(e)}")
            # Không raise e ở đây nếu muốn phát triển local trên CPU mà không bị sập ứng dụng ngay lập tức

    def generate_rag_response(
        self, 
        prompt: str, 
        system_prompt: str, 
        temperature: float = 0.2, 
        max_tokens: int = 512
    ) -> str:
        """
        Sinh câu trả lời cho luồng Q&A RAG chống ảo giác.
        Sử dụng Temperature thấp (0.2) để đảm bảo câu trả lời bám sát Context.
        """
        if not self.llm:
            return "Hệ thống AI Engine chưa sẵn sàng (Thiếu GPU/vLLM)."

        try:
            # Tạo prompt theo chuẩn ChatML format
            full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
            
            sampling_params = SamplingParams(
                temperature=temperature,
                max_tokens=max_tokens,
                stop=["<|im_end|>", "<|endoftext|>"]
            )

            outputs = self.llm.generate([full_prompt], sampling_params)
            response_text = outputs[0].outputs[0].text.strip()
            
            return response_text

        except Exception as e:
            logger.error(f"Lỗi trong quá trình sinh câu trả lời RAG: {str(e)}")
            return "Đã xảy ra lỗi trong quá trình suy luận mô hình."

    def generate_structured_output(
        self, 
        prompt: str, 
        schema_class: type[BaseModel], 
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Thực thi Tool Calling: Ép 100% LLM trả về đúng định dạng JSON theo Pydantic Schema.
        Sử dụng thư viện Outlines để đảm bảo không bị lỗi parse JSON.
        
        :param prompt: Prompt mô tả câu hỏi / bài kiểm tra cần sinh
        :param schema_class: Lớp Pydantic định nghĩa JSON Schema (Quiz Schema, Flashcard Schema)
        """
        if not self.outlines_model:
            raise RuntimeError("vLLM/Outlines Engine chưa được khởi tạo thành công.")

        try:
            # Ép cấu trúc đầu ra bằng Outlines
            generator = generate.json(self.outlines_model, schema_class)
            result_model = generator(prompt, temperature=temperature)

            # Chuyển đổi từ Pydantic Model sang Dictionary
            return result_model.model_dump()

        except JSONDecodeError as e:
            logger.error(f"Lỗi JSON Decode khi Tool Calling: {str(e)}")
            raise ValueError("Mô hình sinh dữ liệu JSON không đúng cấu trúc.") from e
        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi thực thi Structured Output: {str(e)}")
            raise e


# Singleton Instance để dùng chung toàn bộ ứng dụng
llm_engine = LLMEngineManager()