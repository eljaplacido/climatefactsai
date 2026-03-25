"use client";
import { useState, useEffect, createContext, useContext, useCallback, useRef, type ReactNode } from "react";
import { X, CheckCircle2, AlertTriangle, Info } from "lucide-react";

type ToastType = "success" | "error" | "info";
interface ToastItem { id: number; message: string; type: ToastType; }
interface ToastContextValue { showToast: (message: string, type?: ToastType) => void; }

const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++nextId.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
  }, []);

  const dismiss = (id: number) => setToasts(prev => prev.filter(t => t.id !== id));

  const icons = { success: CheckCircle2, error: AlertTriangle, info: Info };
  const colors = { success: "bg-emerald-50 border-emerald-200 text-emerald-800", error: "bg-red-50 border-red-200 text-red-800", info: "bg-blue-50 border-blue-200 text-blue-800" };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 z-[200] space-y-2 max-w-sm">
        {toasts.map(t => {
          const Icon = icons[t.type];
          return (
            <div key={t.id} className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg ${colors[t.type]}`} role="alert">
              <Icon className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <p className="text-sm flex-1">{t.message}</p>
              <button onClick={() => dismiss(t.id)} className="flex-shrink-0" aria-label="Dismiss notification"><X className="h-4 w-4" /></button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
