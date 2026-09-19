import { useState } from "react";
import { requestOtp, verifyOtp } from "../services/auth";

const styles = `
  .login-root {
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
    background: var(--bg); color: var(--text); font-family: 'DM Mono', monospace; padding: 16px;
  }
  .login-card {
    width: 100%; max-width: 380px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; padding: 32px 28px; display: flex; flex-direction: column; gap: 18px;
  }
  .login-logo { display: flex; align-items: center; gap: 10px; }
  .login-logo-icon {
    width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, var(--accent2), var(--accent)); font-size: 18px;
  }
  .login-title { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 20px; letter-spacing: -0.5px; }
  .login-sub { font-size: 12px; color: var(--muted); }
  .login-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--muted); }
  .login-input {
    width: 100%; padding: 12px 14px; border-radius: 10px; border: 1px solid var(--border);
    background: var(--surface2); color: var(--text); font-family: 'DM Mono', monospace; font-size: 14px;
  }
  .login-input:focus { outline: none; border-color: var(--accent); }
  .login-btn {
    padding: 13px; border: none; border-radius: 10px; cursor: pointer; color: #fff;
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    font-family: 'Syne', sans-serif; font-weight: 700; font-size: 14px;
  }
  .login-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .login-link { background: none; border: none; color: var(--muted); font-size: 12px; cursor: pointer; text-decoration: underline; }
  .login-hint {
    font-size: 12px; padding: 10px 12px; border-radius: 10px;
    background: rgba(255,182,39,0.08); border: 1px solid rgba(255,182,39,0.3); color: var(--warning);
  }
  .login-error { font-size: 12px; color: var(--danger); }
`;

function Login({ onLogin }) {
  const [step, setStep] = useState("email"); // email | code
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const sendCode = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setDevCode(await requestOtp(email.trim()));
      setStep("code");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not send a code. Is the API running?");
    } finally {
      setBusy(false);
    }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await verifyOtp(email.trim(), code.trim());
      onLogin(data.access_token);
    } catch (err) {
      setError(err.response?.data?.detail || "That code did not work.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <style>{styles}</style>
      <div className="login-root">
        <form className="login-card" onSubmit={step === "email" ? sendCode : submitCode}>
          <div className="login-logo">
            <div className="login-logo-icon">🧺</div>
            <div>
              <div className="login-title">AutoBasket</div>
              <div className="login-sub">Sign in to your fridge</div>
            </div>
          </div>

          {step === "email" ? (
            <>
              <label className="login-label" htmlFor="email">Email</label>
              <input
                id="email" className="login-input" type="email" autoFocus required
                placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)}
              />
              <button className="login-btn" disabled={busy}>{busy ? "Sending…" : "Send code"}</button>
            </>
          ) : (
            <>
              <div className="login-sub">Code sent to <strong>{email}</strong></div>
              {devCode && <div className="login-hint">Dev mode — your code is <strong>{devCode}</strong></div>}
              <label className="login-label" htmlFor="code">6-digit code</label>
              <input
                id="code" className="login-input" inputMode="numeric" pattern="[0-9]{6}" autoFocus required
                placeholder="123456" value={code} onChange={(e) => setCode(e.target.value)}
              />
              <button className="login-btn" disabled={busy}>{busy ? "Checking…" : "Sign in"}</button>
              <button type="button" className="login-link" onClick={() => { setStep("email"); setCode(""); }}>
                Use a different email
              </button>
            </>
          )}

          {error && <div className="login-error">{error}</div>}
        </form>
      </div>
    </>
  );
}

export default Login;
