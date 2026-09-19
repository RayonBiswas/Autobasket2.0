import { useMemo, useState } from "react";
import API from "../services/api";

function AgentChatPanel() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "I can help review pantry levels, build restock lists, and place orders with a confirmation guardrail.",
    },
  ]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);

  const sessionId = useMemo(() => {
    if (typeof window === "undefined") return "dashboard-session";
    const existing = window.localStorage.getItem("autobasket-agent-session");
    if (existing) return existing;
    const next = `dashboard-${Date.now()}`;
    window.localStorage.setItem("autobasket-agent-session", next);
    return next;
  }, []);

  const handleSend = async () => {
    if (!input.trim() || pending) return;
    const userMessage = input.trim();
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    setPending(true);

    try {
      const res = await API.post("/agent/chat", { message: userMessage, session_id: sessionId });
      setMessages((prev) => [...prev, { role: "assistant", content: res.data.response }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "The agent is temporarily unavailable. Please try again in a moment." }]);
    } finally {
      setPending(false);
    }
  };

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 20, padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontFamily: "'Syne', sans-serif", fontWeight: 800, fontSize: 18 }}>Agent Assistant</div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>LangGraph-style reasoning with Ollama and confirmation guardrails</div>
        </div>
        <div style={{ fontSize: 11, padding: "4px 8px", borderRadius: 999, background: "rgba(0,229,255,0.12)", color: "var(--accent)", border: "1px solid rgba(0,229,255,0.2)" }}>AI</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 260, overflowY: "auto", paddingRight: 4 }}>
        {messages.map((msg, index) => (
          <div key={`${msg.role}-${index}`} style={{ alignSelf: msg.role === "user" ? "flex-end" : "flex-start", maxWidth: "86%" }}>
            <div style={{ background: msg.role === "user" ? "linear-gradient(135deg, var(--accent2), var(--accent))" : "var(--surface2)", color: msg.role === "user" ? "#fff" : "var(--text)", padding: "10px 12px", borderRadius: 14, border: msg.role === "assistant" ? "1px solid var(--border)" : "none", whiteSpace: "pre-wrap" }}>
              {msg.content}
            </div>
          </div>
        ))}
        {pending && <div style={{ alignSelf: "flex-start", color: "var(--muted)", fontSize: 12 }}>Thinking…</div>}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && handleSend()}
          placeholder="Ask about inventory, restocks, or orders"
          style={{ flex: 1, background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 12, color: "var(--text)", padding: "10px 12px", outline: "none" }}
        />
        <button onClick={handleSend} disabled={pending} style={{ border: "none", borderRadius: 12, padding: "10px 14px", background: "linear-gradient(135deg, var(--accent2), var(--accent))", color: "#fff", cursor: pending ? "default" : "pointer", opacity: pending ? 0.7 : 1 }}>
          Send
        </button>
      </div>
    </div>
  );
}

export default AgentChatPanel;
