"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api, authStorage, User } from "@/lib/api";

interface Toast {
  id: string;
  type: "success" | "error" | "info" | "warning";
  message: string;
  duration?: number;
}

interface ToastContextType {
  toasts: Toast[];
  showToast: (message: string, type?: "success" | "error" | "info" | "warning") => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType>({
  toasts: [],
  showToast: () => {},
  removeToast: () => {},
});

export const useToast = () => useContext(ToastContext);

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = (
    message: string,
    type: "success" | "error" | "info" | "warning" = "info"
  ) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const refreshUser = async () => {
    const storedToken = authStorage.getToken();
    if (!storedToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    try {
      const u = await api.getCurrentUser();
      setUser(u);
      setToken(storedToken);
    } catch {
      authStorage.clearToken();
      setUser(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = (newToken: string, newUser: User) => {
    authStorage.setToken(newToken);
    setToken(newToken);
    setUser(newUser);
    showToast(`Welcome back, ${newUser.full_name || newUser.email}!`, "success");
  };

  const logout = () => {
    authStorage.clearToken();
    setToken(null);
    setUser(null);
    queryClient.clear();
    showToast("Signed out successfully", "info");
  };

  return (
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider
        value={{
          user,
          token,
          isAuthenticated: !!user,
          isLoading,
          login,
          logout,
          refreshUser,
        }}
      >
        <ToastContext.Provider value={{ toasts, showToast, removeToast }}>
          {children}

          {/* Toast Notification Container */}
          <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md pointer-events-none">
            {toasts.map((toast) => (
              <div
                key={toast.id}
                className={`pointer-events-auto flex items-center justify-between p-3.5 rounded-xl shadow-2xl border text-sm font-medium transition-all animate-in slide-in-from-bottom-3 duration-200 ${
                  toast.type === "error"
                    ? "bg-rose-950/90 text-rose-200 border-rose-800"
                    : toast.type === "success"
                    ? "bg-emerald-950/90 text-emerald-200 border-emerald-800"
                    : toast.type === "warning"
                    ? "bg-amber-950/90 text-amber-200 border-amber-800"
                    : "bg-slate-900/90 text-slate-100 border-slate-700"
                }`}
              >
                <span>{toast.message}</span>
                <button
                  onClick={() => removeToast(toast.id)}
                  className="ml-3 text-xs opacity-70 hover:opacity-100 px-1"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </ToastContext.Provider>
      </AuthContext.Provider>
    </QueryClientProvider>
  );
}
