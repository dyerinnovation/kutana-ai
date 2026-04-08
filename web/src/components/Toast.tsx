import { useEffect, useState, useCallback } from "react";

interface ToastMessage {
  id: number;
  message: string;
  type: "error" | "success" | "info";
}

let nextId = 0;
let addToastFn: ((msg: Omit<ToastMessage, "id">) => void) | null = null;

export function showToast(message: string, type: ToastMessage["type"] = "error") {
  addToastFn?.({ message, type });
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((msg: Omit<ToastMessage, "id">) => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { ...msg, id }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  useEffect(() => {
    addToastFn = addToast;
    return () => {
      addToastFn = null;
    };
  }, [addToast]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`max-w-sm rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur-sm animate-in slide-in-from-right ${
            t.type === "error"
              ? "border-red-500/30 bg-red-950/90 text-red-200"
              : t.type === "success"
                ? "border-green-500/30 bg-green-950/90 text-green-200"
                : "border-blue-500/30 bg-blue-950/90 text-blue-200"
          }`}
          role="alert"
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}
