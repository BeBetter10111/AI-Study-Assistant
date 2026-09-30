// Giao diện chat tương tác — gọi askQuestion() từ services/api.js
import { useState } from "react";
import { askQuestion } from "../../services/api";

export default function ChatWindow({ documentId = null }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || isLoading) return;

    const userMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await askQuestion(question, documentId);
      const { answer, citations, intent } = response.data;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: answer, citations, intent },
      ]);
    } catch (err) {
      const detail =
        err.response?.data?.detail || "Đã xảy ra lỗi khi kết nối tới trợ lý AI.";
      setError(detail);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.messageList}>
        {messages.length === 0 && (
          <p style={styles.placeholder}>
            Đặt câu hỏi về tài liệu bạn đã tải lên để bắt đầu.
          </p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            style={{
              ...styles.messageBubble,
              ...(message.role === "user" ? styles.userBubble : styles.assistantBubble),
            }}
          >
            <p style={styles.messageText}>{message.content}</p>
            {message.citations && message.citations.length > 0 && (
              <div style={styles.citations}>
                <span style={styles.citationsTitle}>Nguồn trích dẫn:</span>
                <ul style={styles.citationList}>
                  {message.citations.map((citation, cIndex) => (
                    <li key={cIndex} style={styles.citationItem}>
                      [{citation.chunk_index}] {citation.content.slice(0, 140)}
                      {citation.content.length > 140 ? "…" : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
        {isLoading && <p style={styles.placeholder}>Đang suy nghĩ…</p>}
        {error && <p style={styles.error}>{error}</p>}
      </div>

      <div style={styles.inputRow}>
        <textarea
          style={styles.textarea}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhập câu hỏi của bạn…"
          rows={2}
          disabled={isLoading}
        />
        <button
          style={styles.sendButton}
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
        >
          Gửi
        </button>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    border: "1px solid #e2e8f0",
    borderRadius: "8px",
    overflow: "hidden",
  },
  messageList: {
    flex: 1,
    overflowY: "auto",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  placeholder: { color: "#94a3b8", fontStyle: "italic" },
  error: { color: "#dc2626" },
  messageBubble: {
    maxWidth: "80%",
    padding: "10px 12px",
    borderRadius: "10px",
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: "#2563eb",
    color: "#fff",
  },
  assistantBubble: {
    alignSelf: "flex-start",
    backgroundColor: "#f1f5f9",
    color: "#0f172a",
  },
  messageText: { margin: 0, whiteSpace: "pre-wrap" },
  citations: { marginTop: "8px", fontSize: "12px", opacity: 0.85 },
  citationsTitle: { fontWeight: 600 },
  citationList: { margin: "4px 0 0 16px", padding: 0 },
  citationItem: { marginBottom: "4px" },
  inputRow: {
    display: "flex",
    gap: "8px",
    padding: "8px",
    borderTop: "1px solid #e2e8f0",
  },
  textarea: {
    flex: 1,
    resize: "none",
    padding: "8px",
    borderRadius: "6px",
    border: "1px solid #cbd5e1",
    fontFamily: "inherit",
  },
  sendButton: {
    padding: "0 16px",
    borderRadius: "6px",
    border: "none",
    backgroundColor: "#2563eb",
    color: "#fff",
    cursor: "pointer",
  },
};
