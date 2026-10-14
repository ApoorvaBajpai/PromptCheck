"use client";

import React from "react";
import { Run } from "@/lib/api";
import {
  History,
  AlertOctagon,
  CheckCircle2,
  AlertTriangle,
  Play,
  ArrowRight,
  Pin,
  Clock,
} from "lucide-react";

interface RunHistoryChartProps {
  runs: Run[];
  onSelectRun: (run: Run) => void;
  onStartNewRun: () => void;
}

export function RunHistoryChart({
  runs,
  onSelectRun,
  onStartNewRun,
}: RunHistoryChartProps) {
  const completedRuns = runs.filter((r) => r.status === "completed");

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <History className="w-5 h-5 text-indigo-400" />
            <span>Evaluation Runs History ({runs.length})</span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Historical regression trends and pass rates across prompt versions.
          </p>
        </div>

        <button
          onClick={onStartNewRun}
          className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition self-start sm:self-auto"
        >
          <Play className="w-3.5 h-3.5 fill-white" />
          <span>New Run</span>
        </button>
      </div>

      {/* Visual Timeline / Trend Bars */}
      {completedRuns.length > 0 && (
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
            <span>Pass Rate & Regression Timeline (Recent Runs)</span>
            <div className="flex items-center gap-4 text-[11px] font-medium text-slate-400">
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded bg-emerald-500" />
                <span>Passed</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded bg-rose-500" />
                <span>Regression</span>
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded bg-amber-500" />
                <span>Soft Reg</span>
              </span>
            </div>
          </div>

          <div className="h-32 flex items-end gap-2 pt-4 px-2 overflow-x-auto">
            {completedRuns
              .slice(0, 15)
              .reverse()
              .map((r) => {
                const passRate =
                  r.total_tests > 0 ? (r.passed_tests / r.total_tests) * 100 : 0;
                const regCount = r.summary?.regressions ?? 0;
                const softRegCount = r.summary?.soft_regressions ?? 0;

                return (
                  <div
                    key={r.id}
                    onClick={() => onSelectRun(r)}
                    className="flex-1 min-w-[36px] max-w-[60px] flex flex-col items-center gap-1 group cursor-pointer"
                    title={`Run #${r.id}: ${passRate.toFixed(0)}% passed, ${regCount} regressions`}
                  >
                    <div className="w-full bg-slate-950 rounded-t-lg h-24 flex items-end p-0.5 border border-slate-800 group-hover:border-indigo-500 transition">
                      <div
                        className={`w-full rounded-md transition-all ${
                          regCount > 0
                            ? "bg-rose-500"
                            : softRegCount > 0
                            ? "bg-amber-500"
                            : "bg-emerald-500"
                        }`}
                        style={{ height: `${Math.max(15, passRate)}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 group-hover:text-indigo-300">
                      #{r.id}
                    </span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Runs Table */}
      {runs.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
          <History className="w-10 h-10 text-slate-500 mx-auto mb-2" />
          <h3 className="text-sm font-bold text-white mb-1">No Evaluation Runs Yet</h3>
          <p className="text-xs text-slate-400 mb-4 max-w-sm mx-auto">
            Run an evaluation to benchmark your prompt version and catch regressions.
          </p>
          <button
            onClick={onStartNewRun}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition shadow"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>Launch Evaluation Run</span>
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900 shadow-xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4">Run ID</th>
                <th className="py-3 px-4">Prompt Version</th>
                <th className="py-3 px-4">Verdict & Status</th>
                <th className="py-3 px-4">Pass Rate</th>
                <th className="py-3 px-4">Regressions</th>
                <th className="py-3 px-4">Date</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {runs.map((r) => {
                const regCount = r.summary?.regressions ?? 0;
                const softRegCount = r.summary?.soft_regressions ?? 0;
                const isPassed = r.failed_tests === 0 && regCount === 0;

                return (
                  <tr
                    key={r.id}
                    onClick={() => onSelectRun(r)}
                    className="hover:bg-slate-800/40 cursor-pointer transition"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-white">
                      #{r.id}
                    </td>

                    <td className="py-3 px-4 font-mono text-slate-300">
                      v{r.prompt_version_id}
                    </td>

                    <td className="py-3 px-4">
                      {r.status === "completed" ? (
                        regCount > 0 ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-rose-300 bg-rose-950/60 border border-rose-800 px-2 py-0.5 rounded-full">
                            <AlertOctagon className="w-3 h-3 text-rose-400" />
                            <span>❌ Regression</span>
                          </span>
                        ) : softRegCount > 0 ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-300 bg-amber-950/60 border border-amber-800 px-2 py-0.5 rounded-full">
                            <AlertTriangle className="w-3 h-3 text-amber-400" />
                            <span>⚠️ Soft Reg</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-300 bg-emerald-950/60 border border-emerald-800 px-2 py-0.5 rounded-full">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            <span>🟢 Passed</span>
                          </span>
                        )
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono text-slate-400 bg-slate-950 border border-slate-800 px-2 py-0.5 rounded-full">
                          {r.status}
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 font-mono font-semibold">
                      {r.passed_tests} / {r.total_tests} (
                      {r.total_tests > 0
                        ? `${Math.round((r.passed_tests / r.total_tests) * 100)}%`
                        : "0%"}
                      )
                    </td>

                    <td className="py-3 px-4 font-mono">
                      {regCount > 0 ? (
                        <span className="text-rose-400 font-bold">{regCount}</span>
                      ) : (
                        <span className="text-slate-500">0</span>
                      )}
                    </td>

                    <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                      {new Date(r.created_at).toLocaleString()}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectRun(r);
                        }}
                        className="flex items-center gap-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300 ml-auto"
                      >
                        <span>Report</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
