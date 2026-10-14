"use client";

import React, { useState } from "react";
import { PromptItem, PromptVersion, Run, api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { Play, X, Layers, Database, ShieldCheck, AlertCircle } from "lucide-react";

interface RunConfirmationDialogProps {
  projectId: number;
  prompts: PromptItem[];
  runs: Run[];
  activeVersionId?: number | null;
  totalActiveTests: number;
  hasApiKey: boolean;
  onClose: () => void;
  onRunCreated: (run: Run) => void;
  onOpenSettings: () => void;
}

export function RunConfirmationDialog({
  projectId,
  prompts,
  runs,
  activeVersionId,
  totalActiveTests,
  hasApiKey,
  onClose,
  onRunCreated,
  onOpenSettings,
}: RunConfirmationDialogProps) {
  const { showToast } = useToast();

  // Find all prompt versions across prompts
  const allVersions: Array<{ promptName: string; version: PromptVersion }> = [];
  prompts.forEach((p) => {
    (p.versions || []).forEach((v) => {
      allVersions.push({ promptName: p.name, version: v });
    });
  });

  const [selectedVersionId, setSelectedVersionId] = useState<number>(
    activeVersionId || (allVersions[0]?.version.id ?? 1)
  );

  const completedRuns = runs.filter((r) => r.status === "completed");
  const [selectedBaselineId, setSelectedBaselineId] = useState<string>("auto");
  const [enableCache, setEnableCache] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasApiKey) {
      showToast("Please configure your Gemini API Key before running evaluations", "warning");
      onOpenSettings();
      onClose();
      return;
    }

    setIsSubmitting(true);
    try {
      const baselineId =
        selectedBaselineId === "auto" ? null : Number(selectedBaselineId);

      const run = await api.createRun(projectId, {
        prompt_version_id: selectedVersionId,
        enable_cache: enableCache,
        baseline_run_id: baselineId || undefined,
      });

      showToast(`Run #${run.id} queued successfully!`, "success");
      onRunCreated(run);
      onClose();
    } catch (err: any) {
      showToast(err.message || "Failed to start evaluation run", "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-950/60 text-indigo-400 border border-indigo-800/80">
              <Play className="w-5 h-5 fill-indigo-400" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Start Evaluation Run</h3>
              <p className="text-xs text-slate-400">
                Execute prompt suite against all active test cases.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {!hasApiKey && (
          <div className="mb-4 p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/80 text-amber-200 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold block">No Gemini API Key Configured</span>
              <span className="text-slate-300">
                You need a Gemini API Key to run live evaluations.
              </span>
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenSettings();
                }}
                className="block mt-1 font-semibold text-amber-400 hover:underline"
              >
                Configure Gemini API Key &rarr;
              </button>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Version Selection */}
          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1">
              Select Prompt Version to Evaluate *
            </label>
            <select
              value={selectedVersionId}
              onChange={(e) => setSelectedVersionId(Number(e.target.value))}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {allVersions.map(({ promptName, version }) => (
                <option key={version.id} value={version.id}>
                  {promptName} — v{version.version_number} (
                  {version.commit_message || "no message"})
                </option>
              ))}
            </select>
          </div>

          {/* Baseline Selection */}
          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1 flex items-center justify-between">
              <span>Baseline Run for Regression Comparison</span>
              <span className="text-[10px] text-slate-500 font-mono">
                Auto = Project / Previous run
              </span>
            </label>
            <select
              value={selectedBaselineId}
              onChange={(e) => setSelectedBaselineId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
            >
              <option value="auto">
                ⚡ Auto-detect (Project baseline / Latest completed run)
              </option>
              {completedRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  Run #{r.id} (
                  {new Date(r.created_at).toLocaleDateString()}) —{" "}
                  {r.passed_tests}/{r.total_tests} passed
                </option>
              ))}
            </select>
          </div>

          {/* Output Cache Toggle */}
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-cyan-400" />
              <div>
                <span className="font-semibold text-white block">
                  Enable Output Caching
                </span>
                <span className="text-[11px] text-slate-500">
                  Reuse identical model generations to save latency and token costs.
                </span>
              </div>
            </div>
            <input
              type="checkbox"
              checked={enableCache}
              onChange={(e) => setEnableCache(e.target.checked)}
              className="w-4 h-4 rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-indigo-500"
            />
          </div>

          {/* Scope Preview */}
          <div className="p-3 rounded-xl bg-indigo-950/30 border border-indigo-900/50 flex items-center justify-between text-xs text-indigo-300">
            <span>Tests to execute:</span>
            <span className="font-bold text-white font-mono text-sm">
              {totalActiveTests} active test cases
            </span>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || totalActiveTests === 0}
              className="flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition disabled:opacity-40"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              <span>{isSubmitting ? "Queueing Run..." : "Execute Run"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
