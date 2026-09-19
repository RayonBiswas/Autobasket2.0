import API from "./api";

const TOKEN_KEY = "ab_token";

// localStorage can throw (private mode, blocked storage); the app must still work without it.
export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export async function requestOtp(email) {
  const res = await API.post("/auth/request-otp", { email });
  return res.data?.dev_code ?? null;
}

export async function verifyOtp(email, code) {
  const res = await API.post("/auth/verify-otp", { email, code });
  setToken(res.data.access_token);
  return res.data;
}
