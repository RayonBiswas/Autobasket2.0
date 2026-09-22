import axios from "axios";

// Set VITE_API_URL in frontend/.env.local for a non-local backend (see .env.example).
// Production builds default to /api on the same origin, which Caddy proxies to the API container.
const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || (import.meta.env.PROD ? "/api" : "http://127.0.0.1:8000"),
});

const TOKEN_KEY = "ab_token";

API.interceptors.request.use((config) => {
  let token = null;
  try {
    token = localStorage.getItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// A 401 means the token is missing/expired: drop it and let the app show the login screen.
API.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !err.config?.url?.startsWith("/auth/")) {
      try {
        localStorage.removeItem(TOKEN_KEY);
      } catch {
        /* ignore */
      }
      window.dispatchEvent(new Event("ab:logout"));
    }
    return Promise.reject(err);
  }
);

export default API;
