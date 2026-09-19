import { useState } from "react";
import { requestOtp, verifyOtp } from "../services/auth";

const styles = `
  .login { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
  .login-card { width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: 20px; }
  .login-card h1 { font-size: 1.75rem; }
  .login-card .lead { color: var(--muted); margin-top: 6px; }
  .login-code { font-size: 1.5rem; letter-spacing: 0.25em; }
  .login-error { color: var(--danger); font-size: 14px; }
  .login-theme { position: fixed; top: 16px; right: 16px; }
`;

function Login({ onLogin, theme, onToggleTheme }) {
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
      setError(err.response?.data?.detail || "We couldn't send a code. Check that the app is running and try again.");
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
      setError(err.response?.data?.detail || "That code didn't match. Check the digits and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <style>{styles}</style>
      <button className="btn btn-ghost btn-sm login-theme" onClick={onToggleTheme}>
        {theme === "dark" ? "Light mode" : "Dark mode"}
      </button>
      <div className="login">
        <form className="login-card card" onSubmit={step === "email" ? sendCode : submitCode}>
          <div>
            <h1>Welcome to AutoBasket</h1>
            <p className="lead">
              {step === "email" ? "Enter your email and we'll send a sign-in code." : `We sent a 6-digit code to ${email}.`}
            </p>
          </div>

          {step === "email" ? (
            <>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input id="email" className="input" type="email" autoFocus required autoComplete="email"
                  placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Sending code…" : "Send code"}</button>
            </>
          ) : (
            <>
              {devCode && (
                <div className="notice notice-ok">
                  Development mode: your code is <strong className="login-code">{devCode}</strong>
                </div>
              )}
              <div className="field">
                <label htmlFor="code">Sign-in code</label>
                <input id="code" className="input" inputMode="numeric" pattern="[0-9]{6}" autoFocus required
                  autoComplete="one-time-code" placeholder="123456" value={code} onChange={(e) => setCode(e.target.value)} />
              </div>
              <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
              <button type="button" className="btn btn-ghost" onClick={() => { setStep("email"); setCode(""); }}>
                Use a different email
              </button>
            </>
          )}

          {error && <div className="login-error" role="alert">{error}</div>}
        </form>
      </div>
    </>
  );
}

export default Login;
