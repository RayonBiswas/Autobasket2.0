import axios from "axios";

// Set VITE_API_URL in frontend/.env.local for a non-local backend (see .env.example).
const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
});

export default API;
