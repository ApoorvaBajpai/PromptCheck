"use client";

import React, { useState } from "react";
import { Project, api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { KeyRound, ShieldCheck, CheckCircle2, AlertTriangle, Eye, EyeOff, ExternalLink } from "lucide-react";

interface ApiKeySettingsProps {
  project: Project;
  onRefresh: () => void;
}

export function ApiKeySettings({ project, onRefresh }: ApiKeySettingsProps) {
  const { showToast } = useToast();

  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasKey, setHasKey] = React.useState(project.has_api_key);

  React.useEffect(() => {
    setHasKey(project.has_api_key);
  }, [project.has_api_key]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;

    setIsSaving(true);
    try {
      await api.setProjectApiKey(project.id, apiKey.trim());
      setHasKey(true);
      showToast("Gemini API key encrypted and saved successfully!", "success");
      setApiKey("");
      onRefresh();
    } catch (err: any) {
      showToast(err.message || "Failed to update Gemini API key", "error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-in fade-in duration-200">
      {/* Status Card */}
      <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <KeyRound className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-bold text-white">Gemini API Key Settings</h3>
          </div>

          {hasKey ? (
            <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-400 bg-emerald-950/60 border border-emerald-800 px-3 py-1 rounded-full">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Configured & Encrypted</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs font-semibold text-amber-400 bg-amber-950/60 border border-amber-800 px-3 py-1 rounded-full animate-pulse">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>No API Key Configured</span>
            </span>
          )}
        </div>

        <p className="text-xs text-slate-300 leading-relaxed">
          PromptCheck uses Google Gemini to generate model outputs, compute semantic vector embeddings, and execute LLM-as-judge rubrics.
        </p>

        {/* Encryption Assurance Badge */}
        <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 flex items-start gap-3 text-xs text-slate-400">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <span className="font-bold text-slate-200 block">
              AES-128 Fernet Encryption At Rest
            </span>
            <span>
              Your API key is securely encrypted before being written to PostgreSQL and is never exposed in plaintext over API responses.
            </span>
          </div>
        </div>

        {/* Key Form */}
        <form onSubmit={handleSave} className="space-y-4 pt-2">
          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1.5 flex items-center justify-between">
              <span>{project.has_api_key ? "Update API Key" : "Enter API Key"} *</span>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
              >
                <span>Get API key from Google AI Studio</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </label>

            <div className="relative">
              <input
                type={showKey ? "text" : "password"}
                required
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="AIzaSy... or AQ.Ab8..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-3.5 pr-10 py-2.5 text-xs font-mono text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300"
              >
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSaving || !apiKey.trim()}
            className="flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition disabled:opacity-40"
          >
            <KeyRound className="w-3.5 h-3.5" />
            <span>{isSaving ? "Encrypting & Saving..." : "Save Encrypted API Key"}</span>
          </button>
        </form>
      </div>
    </div>
  );
}
