// Axios API calls kết nối thẳng FastAPI
import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

// Gắn/gỡ JWT cho mọi request tiếp theo sau khi đăng nhập/đăng ký.
export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
};

export const registerUser = (email, password) =>
  api.post("/auth/register", { email, password });

export const loginUser = (email, password) =>
  api.post("/auth/login", { email, password });

export const uploadDocument = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/documents/upload", form);
};

export const getDocumentStatus = (documentId) =>
  api.get(`/documents/${documentId}/status`);

// Trước đây backend nhận `question`/`topic` như query param (FastAPI suy ra
// từ tham số hàm không có Pydantic model), trong khi hàm này lại gửi JSON
// body — 2 phía không khớp nhau nên request luôn lỗi 422. Endpoint đã được
// cập nhật để nhận đúng JSON body như bên dưới.
export const askQuestion = (question, documentId = null, topK = 4) =>
  api.post("/chat/query", {
    question,
    document_id: documentId,
    top_k: topK,
  });

export const generateQuiz = (topic, numQuestions = 10, documentId = null) =>
  api.post("/quiz/generate", {
    topic,
    num_questions: numQuestions,
    document_id: documentId,
  });

export const submitQuizResult = (quizId, result) =>
  api.post(`/quiz/${quizId}/submit`, result);
