"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth, useToast } from "@/components/providers";
import { Layers, Lock, Mail, User as UserIcon, ArrowRight, Sparkles } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const { showToast } = useToast();

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("user1@example.com");
  const [password, setPassword] = useState("password123");
  const [fullName, setFullName] = useState("Demo Engineer");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      if (mode === "signup") {
        await api.register({ email, password, full_name: fullName });
        showToast("Account created successfully! Signing in...", "success");
      }

      // Login to obtain JWT
      const authData = await api.login(email, password);
      // Fetch user profile
      const userProfile = await api.getCurrentUser();
      login(authData.access_token, userProfile);
      router.push("/");
    } catch (err: any) {
      setErrorMsg(err.message || "Authentication failed. Please check your credentials.");
      showToast(err.message || "Authentication failed", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setEmail("user1@example.com");
    setPassword("password123");
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const authData = await api.login("user1@example.com", "password123");
      const userProfile = await api.getCurrentUser();
      login(authData.access_token, userProfile);
      router.push("/");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to log in with demo credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 relative overflow-hidden">
      {/* Background ambient glow */}
      <div className="absolute top-1/4 -left-20 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-cyan-600/15 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md z-10">
        {/* Header Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-600 to-cyan-500 shadow-xl shadow-indigo-500/20 mb-3">
            <Layers className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">
            PromptCheck
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Continuous prompt regression testing & quality evaluation
          </p>
        </div>

        {/* Card */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
          {/* Mode Tabs */}
          <div className="flex border-b border-slate-800 mb-6 pb-2">
            <button
              type="button"
              onClick={() => {
                setMode("signin");
                setErrorMsg(null);
              }}
              className={`flex-1 pb-2 text-sm font-semibold transition border-b-2 -mb-2.5 ${
                mode === "signin"
                  ? "border-indigo-500 text-white"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setErrorMsg(null);
              }}
              className={`flex-1 pb-2 text-sm font-semibold transition border-b-2 -mb-2.5 ${
                mode === "signup"
                  ? "border-indigo-500 text-white"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              Create Account
            </button>
          </div>

          {errorMsg && (
            <div className="mb-4 p-3 rounded-lg bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2">
              <span>⚠️</span>
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Full Name
                </label>
                <div className="relative">
                  <UserIcon className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alice Johnson"
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="engineer@company.com"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-medium py-2.5 px-4 rounded-xl shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <span>{mode === "signin" ? "Sign In" : "Get Started"}</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Login */}
          <div className="mt-6 pt-5 border-t border-slate-800">
            <button
              type="button"
              onClick={handleDemoLogin}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-2 px-3 text-xs font-semibold text-slate-300 hover:text-white bg-slate-950/70 hover:bg-slate-800 border border-slate-800 rounded-xl transition"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>One-Click Demo Login (Preloaded User)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
