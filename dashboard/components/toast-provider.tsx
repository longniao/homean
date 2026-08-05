"use client";

import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

type Toast = { id: number; message: string; tone: "success" | "error" };
type ToastContextValue = {
  success: (message: string) => void;
  error: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const t = useTranslations("Common");
  const [toasts, setToasts] = useState<Toast[]>([]);

  const add = useCallback((message: string, tone: Toast["tone"]) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(
      () => setToasts((current) => current.filter((toast) => toast.id !== id)),
      4500,
    );
  }, []);
  const value = useMemo(
    () => ({
      success: (message: string) => add(message, "success"),
      error: (message: string) => add(message, "error"),
    }),
    [add],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 top-4 z-[100] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            className="pointer-events-auto flex items-start gap-3 rounded-2xl border bg-white p-4 shadow-xl shadow-stone-900/10"
            key={toast.id}
          >
            {toast.tone === "success" ? (
              <CheckCircle2 className="mt-0.5 size-5 text-emerald-700" />
            ) : (
              <AlertCircle className="mt-0.5 size-5 text-red-700" />
            )}
            <p className="flex-1 text-sm leading-5 text-stone-700">{toast.message}</p>
            <button
              aria-label={t("close")}
              className="text-stone-400 hover:text-stone-700"
              onClick={() =>
                setToasts((current) =>
                  current.filter((item) => item.id !== toast.id),
                )
              }
              type="button"
            >
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used within ToastProvider");
  return value;
}
