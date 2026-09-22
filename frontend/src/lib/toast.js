import { createContext, useContext } from "react";

export const ToastContext = createContext(() => {});

export function useToast() {
  return useContext(ToastContext);
}

// Turns an axios error into a sentence a person can act on.
export function errorText(err, fallback) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  if (!err?.response) return "The app can't reach the server. Check that it is running and try again.";
  return fallback;
}
