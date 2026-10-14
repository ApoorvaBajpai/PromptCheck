"use client";

import React, { useEffect, useState } from "react";
import { API_BASE_URL, Run, api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { Loader2, StopCircle, CheckCircle2, XCircle, Activity } from "lucide-react";

interface LiveRunProgressProps {
  run: Run;
  onCompleted: (updatedRun: Run) => void;
  onCancelled: () => void;
}

export function LiveRunProgress({
  run,
  onCompleted,
  onCancelled,
}: LiveRunProgressProps) {
  const { showToast } = useToast();

  const [passed, setPassed] = useState(run.passed_tests);
  const [failed, setFailed] = useState(run.failed_tests);
  const [total, setTotal] = useState(run.total_tests || 1);
  const [recentOutput, setRecentOutput] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  useEffect(() => {
    // Open Server-Sent Events stream
    const sseUrl = `${API_BASE_URL}/api/runs/${run.id}/stream`;
    const eventSource = new EventSource(sseUrl);

    eventSource.addEventListener("run_progress", (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.passed !== undefined) setPassed(data.passed);
        if (data.failed !== undefined) setFailed(data.failed);
        if (data.total !== undefined) setTotal(data.total);
      } catch {}
    });

    eventSource.addEventListener("test_result", (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.output) {
          setRecentOutput(data.output.slice(0, 140) + "...");
        }
      } catch {}
    });

    eventSource.addEventListener("run_completed", async () => {
      eventSource.close();
      showToast(`Run #${run.id} evaluation completed!`, "success");
      try {
        const updated = await api.getRun(run.id);
        onCompleted(updated);
      } catch {
        onCancelled();
      }
    });

    eventSource.addEventListener("run_cancelled", () => {
      eventSource.close();
      showToast(`Run #${run.id} was cancelled`, "info");
      onCancelled();
    });

    eventSource.onerror = async () => {
      // If SSE errors or closes, poll run status once
      try {
        const updated = await api.getRun(run.id);
        if (updated.status === "completed") {
          eventSource.close();
          onCompleted(updated);
        } else if (updated.status === "cancelled") {
          eventSource.close();
          onCancelled();
        }
      } catch {}
    };

    return () => {
      eventSource.close();
    };
  }, [run.id]);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await api.cancelRun(run.id);
      showToast(`Cancelled Run #${run.id}`, "info");
      onCancelled();
    } catch (err: any) {
      showToast(err.message || "Failed to cancel run", "error");
    } finally {
      setIsCancelling(false);
    }
  };

  const completed = passed + failed;
  const progressPercent = Math.min(100, Math.round((completed / Math.max(1, total)) * 100));

  return (
    <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl space-y-5 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-950/60 border border-indigo-800/80 text-indigo-400 flex items-center justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white">
                Executing Evaluation Run #{run.id}
              </h3>
              <span className="flex items-center gap-1 text-[11px] font-semibold text-cyan-400 bg-cyan-950/40 border border-cyan-800/60 px-2 py-0.5 rounded-full animate-pulse">
                <Activity className="w-3 h-3" />
                <span>Live SSE Streaming</span>
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Evaluating prompt assertions with bounded concurrency & rate limiting.
            </p>
          </div>
        </div>

        <button
          onClick={handleCancel}
          disabled={isCancelling}
          className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-rose-300 hover:text-white bg-rose-950/40 hover:bg-rose-950 border border-rose-800 rounded-xl transition self-start sm:self-auto disabled:opacity-40"
        >
          <StopCircle className="w-4 h-4" />
          <span>{isCancelling ? "Cancelling..." : "Cancel Run"}</span>
        </button>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>
            Progress: {completed} / {total} tests ({progressPercent}%)
          </span>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1 text-emerald-400 font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{passed} passed</span>
            </span>
            <span className="flex items-center gap-1 text-rose-400 font-semibold">
              <XCircle className="w-3.5 h-3.5" />
              <span>{failed} failed</span>
            </span>
          </div>
        </div>

        <div className="w-full h-3 rounded-full bg-slate-950 border border-slate-800 overflow-hidden relative">
          <div
            className="h-full bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 transition-all duration-300 rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {/* Live Activity Stream Snippet */}
      {recentOutput && (
        <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 text-xs font-mono text-slate-400 truncate">
          <span className="text-slate-600 mr-2">Latest output:</span>
          <span className="text-slate-300">{recentOutput}</span>
        </div>
      )}
    </div>
  );
}
