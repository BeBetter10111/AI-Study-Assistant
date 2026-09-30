// Khung ứng dụng — ráp ChatWindow, QuizPlayer, FlashcardDeck lại với nhau,
// cùng một form đăng nhập/đăng ký đơn giản và khu vực upload tài liệu.
import { useState } from "react";
import {
  registerUser,
  loginUser,
  setAuthToken,
  uploadDocument,
  getDocumentStatus,
} from "./services/api";
import ChatWindow from "./features/chatbot/ChatWindow";
import QuizPlayer from "./features/quiz/QuizPlayer";
import FlashcardDeck from "./features/flashcard/FlashcardDeck";

const TABS = [
  { key: "chat", label: "Hỏi đáp" },
  { key: "quiz", label: "Quiz" },
  { key: "flashcard", label: "Thẻ ghi nhớ" },
];

function LoginPanel({ onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleAuth = async (action) => {
    if (!email.trim() || !password.trim() || isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      const response =
        action === "register"
          ? await registerUser(email.trim(), password)
          : await loginUser(email.trim(), password);
      const { access_token: token } = response.data;
      setAuthToken(token);
      onAuthenticated(email.trim(), token);
    } catch (err) {
      setError(err.response?.data?.detail || "Đăng nhập/đăng ký thất bại.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={styles.loginBox}>
      <h2 style={{ marginTop: 0 }}>Đăng nhập / Đăng ký</h2>
      <input
        style={styles.input}
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        style={styles.input}
        placeholder="Mật khẩu (tối thiểu 8 ký tự)"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <div style={{ display: "flex", gap: "8px" }}>
        <button style={styles.primaryButton} onClick={() => handleAuth("login")} disabled={isLoading}>
          Đăng nhập
        </button>
        <button style={styles.secondaryButton} onClick={() => handleAuth("register")} disabled={isLoading}>
          Đăng ký
        </button>
      </div>
      {error && <p style={styles.error}>{error}</p>}
    </div>
  );
}

export default function App() {
  const [userEmail, setUserEmail] = useState(null);
  const [activeTab, setActiveTab] = useState("chat");
  const [documentId, setDocumentId] = useState(null);
  const [documentStatus, setDocumentStatus] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const handleAuthenticated = (email) => setUserEmail(email);

  const handleLogout = () => {
    setAuthToken(null);
    setUserEmail(null);
    setDocumentId(null);
    setDocumentStatus(null);
  };

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setDocumentStatus("uploading");
    try {
      const response = await uploadDocument(file);
      setDocumentId(response.data.document_id);
      setDocumentStatus(response.data.status);
    } catch (err) {
      setUploadError(err.response?.data?.detail || "Tải tài liệu thất bại.");
      setDocumentStatus(null);
    }
  };

  const handleCheckStatus = async () => {
    if (!documentId) return;
    const response = await getDocumentStatus(documentId);
    setDocumentStatus(response.data.status);
  };

  if (!userEmail) {
    return (
      <div style={styles.page}>
        <LoginPanel onAuthenticated={handleAuthenticated} />
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.title}>AI Study Assistant</h1>
        <div>
          <span style={{ marginRight: "12px" }}>{userEmail}</span>
          <button style={styles.secondaryButton} onClick={handleLogout}>
            Đăng xuất
          </button>
        </div>
      </header>

      <section style={styles.uploadRow}>
        <input type="file" accept=".pdf,.docx,.pptx" onChange={handleFileChange} />
        {documentId && (
          <span style={styles.statusBadge}>
            Tài liệu: {documentId.slice(0, 8)}… — trạng thái: {documentStatus}
            <button style={styles.linkButton} onClick={handleCheckStatus}>
              Làm mới
            </button>
          </span>
        )}
        {uploadError && <span style={styles.error}>{uploadError}</span>}
      </section>

      <nav style={styles.tabs}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            style={{
              ...styles.tabButton,
              ...(activeTab === tab.key ? styles.tabButtonActive : {}),
            }}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main style={styles.main}>
        {activeTab === "chat" && <ChatWindow documentId={documentId} />}
        {activeTab === "quiz" && <QuizPlayer documentId={documentId} />}
        {activeTab === "flashcard" && <FlashcardDeck documentId={documentId} />}
      </main>
    </div>
  );
}

const styles = {
  page: {
    fontFamily: "system-ui, sans-serif",
    maxWidth: "760px",
    margin: "0 auto",
    padding: "16px",
    minHeight: "100vh",
    boxSizing: "border-box",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
  },
  title: { fontSize: "20px", margin: 0 },
  loginBox: {
    maxWidth: "320px",
    margin: "80px auto",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    padding: "24px",
    border: "1px solid #e2e8f0",
    borderRadius: "10px",
  },
  input: {
    padding: "8px",
    borderRadius: "6px",
    border: "1px solid #cbd5e1",
  },
  primaryButton: {
    flex: 1,
    padding: "8px 16px",
    borderRadius: "6px",
    border: "none",
    backgroundColor: "#2563eb",
    color: "#fff",
    cursor: "pointer",
  },
  secondaryButton: {
    padding: "8px 16px",
    borderRadius: "6px",
    border: "1px solid #cbd5e1",
    backgroundColor: "#fff",
    cursor: "pointer",
  },
  linkButton: {
    marginLeft: "8px",
    border: "none",
    background: "none",
    color: "#2563eb",
    cursor: "pointer",
    textDecoration: "underline",
  },
  error: { color: "#dc2626" },
  uploadRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    marginBottom: "12px",
    flexWrap: "wrap",
  },
  statusBadge: { fontSize: "14px", color: "#475569" },
  tabs: { display: "flex", gap: "8px", marginBottom: "12px" },
  tabButton: {
    padding: "8px 16px",
    borderRadius: "6px",
    border: "1px solid #cbd5e1",
    backgroundColor: "#fff",
    cursor: "pointer",
  },
  tabButtonActive: { backgroundColor: "#2563eb", color: "#fff", borderColor: "#2563eb" },
  main: { minHeight: "420px" },
};
