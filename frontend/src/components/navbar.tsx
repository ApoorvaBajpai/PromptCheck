"use client";

import React from "react";
import { Project } from "@/lib/api";
import { useAuth } from "./providers";
import {
  Layers,
  KeyRound,
  CheckCircle2,
  AlertTriangle,
  LogOut,
  FolderOpen,
} from "lucide-react";

interface NavbarProps {
  currentProject: Project | null;
  onSelectProjectList: () => void;
  onOpenSettings?: () => void;
}

export function Navbar({
  currentProject,
  onSelectProjectList,
  onOpenSettings,
}: NavbarProps) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand & Project Selector */}
        <div className="flex items-center gap-4">
          <button
            onClick={onSelectProjectList}
            className="flex items-center gap-2.5 group transition-transform active:scale-95 text-left"
          >
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/25">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <span className="text-base font-bold bg-gradient-to-r from-white to-slate-300 bg-clip-text text-transparent">
                PromptCheck
              </span>
              <span className="text-[10px] font-mono text-cyan-400 block -mt-1 tracking-wider uppercase">
                v0.1.0 • Phase 5
              </span>
            </div>
          </button>

          {currentProject && (
            <div className="hidden sm:flex items-center gap-2 pl-4 border-l border-slate-800">
              <button
                onClick={onSelectProjectList}
                className="flex items-center gap-2 text-xs font-medium text-slate-300 hover:text-white px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition"
                title="Switch Project"
              >
                <FolderOpen className="w-3.5 h-3.5 text-indigo-400" />
                <span className="max-w-[180px] truncate font-semibold">
                  {currentProject.name}
                </span>
                <span className="text-[10px] text-slate-500">▼</span>
              </button>
            </div>
          )}
        </div>

        {/* Right side: API Key status & User profile */}
        <div className="flex items-center gap-3">
          {currentProject && (
            <button
              onClick={onOpenSettings}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition ${
                currentProject.has_api_key
                  ? "bg-emerald-950/40 text-emerald-300 border-emerald-800/80 hover:bg-emerald-950/70"
                  : "bg-amber-950/40 text-amber-300 border-amber-800/80 hover:bg-amber-950/70 animate-pulse"
              }`}
            >
              <KeyRound className="w-3.5 h-3.5" />
              {currentProject.has_api_key ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>API Key Configured</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  <span>Set Gemini API Key</span>
                </>
              )}
            </button>
          )}

          {user && (
            <div className="flex items-center gap-2.5 pl-3 border-l border-slate-800">
              <div className="hidden md:block text-right">
                <p className="text-xs font-medium text-slate-200">
                  {user.full_name || "User"}
                </p>
                <p className="text-[11px] text-slate-500 truncate max-w-[160px]">
                  {user.email}
                </p>
              </div>
              <button
                onClick={logout}
                className="p-2 rounded-lg text-slate-400 hover:text-rose-300 hover:bg-rose-950/40 border border-transparent hover:border-rose-900/50 transition"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
