import { useMemo, useState } from "react";
import API from "../services/api";

const styles = `
  .chat { display: flex; flex-direction: column; gap: 14px; }
  .chat-log { display: flex; flex-direction: column; gap: 8px; max-height: 260px; overflow-y: auto; }
  .chat-msg { max-width: 82%; padding: 10px 14px; border-radius: 14px; font-size: 15px; white-space: pre-wrap; line-height: 1.45; }
  .chat-msg.user { align-self: flex-end; background: var(--accent); color: var(--on-accent); border-bottom-right-radius: 4px; }
  .chat-msg.assistant { align-self: flex-start; background: var(--surface-2); border-bottom-left-radius: 4px; }
  .chat-row { display: flex; gap: 8px; }
  .chat-row .input { flex: 1; }
  .chat-hints { display: flex; gap: 8px; flex-wrap: wrap; }
`;

const HINTS = ["What's running low?", "Where is milk cheapest?", "Show my recent orders"];

function AgentChatPanel() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Ask me what's running low, where something is cheapest, or to order it." },
  ]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);

  const sessionId = useMemo(() => {
    try {
      const existing = localStorage.getItem("autobasket-agent-session");
      if (existing) return existing;
      const next = `web-${Date.now()}`;
      localStorage.setItem("autobasket-agent-session", next);
      return next;
    } catch {
      return "web-session";
    }
  }, []);

  const send = async (text) => {
    const userMessage = (text ?? input).trim();
    if (!userMessage || pending) return;
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    setPending(true);
    try {
      const res = await API.post("/agent/chat", { message: userMessage, session_id: sessionId });
      setMessages((prev) => [...prev, { role: "assistant", content: res.data.response }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "I couldn't reach the fridge just now. Try again in a moment." }]);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="card chat">
      <style>{styles}</style>
      <div className="section-title" style={{ marginBottom: 0 }}>
        <h2>Ask your fridge</h2>
        <span className="hide-sm">Orders over ₹50 always ask you first</span>
      </div>
      <div className="chat-log">
        {messages.map((msg, index) => (
          <div key={`${msg.role}-${index}`} className={`chat-msg ${msg.role}`}>{msg.content}</div>
        ))}
        {pending && <div className="muted small">Thinking…</div>}
      </div>
      {messages.length === 1 && (
        <div className="chat-hints">
          {HINTS.map((h) => <button key={h} className="btn btn-sm" onClick={() => send(h)}>{h}</button>)}
        </div>
      )}
      <div className="chat-row">
        <input
          className="input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Type a question"
          aria-label="Ask your fridge"
        />
        <button className="btn btn-primary" onClick={() => send()} disabled={pending}>Send</button>
      </div>
    </div>
  );
}

export default AgentChatPanel;
