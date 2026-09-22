import { useCallback, useEffect, useState } from "react";
import { ToastContext } from "../lib/toast";

// One quiet status line at the bottom of the screen. Replaces alert() everywhere.
export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null);

  const notify = useCallback((message, tone = "info") => setToast({ message, tone, id: Date.now() }), []);

  useEffect(() => {
    if (!toast) return undefined;
    const id = setTimeout(() => setToast(null), toast.tone === "error" ? 6000 : 4000);
    return () => clearTimeout(id);
  }, [toast]);

  return (
    <ToastContext.Provider value={notify}>
      {children}
      {toast && (
        <div className={`toast toast-${toast.tone}`} role={toast.tone === "error" ? "alert" : "status"}>
          {toast.message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
