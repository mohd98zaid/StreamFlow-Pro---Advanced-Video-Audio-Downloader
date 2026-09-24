import { create } from "zustand";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastStore {
  toasts: ToastItem[];
  addToast: (toast: Omit<ToastItem, "id">) => void;
  removeToast: (id: string) => void;
  success: (message: string, title?: string) => void;
  error: (message: string, title?: string) => void;
  info: (message: string, title?: string) => void;
  warning: (message: string, title?: string) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = Math.random().toString(36).substring(2, 9);
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    const dur = toast.duration ?? (toast.type === "error" ? 6000 : 4000);
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, dur);
  },
  removeToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
  },
  success: (message, title) => {
    useToastStore.getState().addToast({ type: "success", message, title });
  },
  error: (message, title) => {
    useToastStore.getState().addToast({ type: "error", message, title });
  },
  info: (message, title) => {
    useToastStore.getState().addToast({ type: "info", message, title });
  },
  warning: (message, title) => {
    useToastStore.getState().addToast({ type: "warning", message, title });
  },
}));
