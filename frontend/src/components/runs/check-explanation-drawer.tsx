"use client";

import React from "react";
import { RunResult } from "@/lib/api";
import { X, CheckCircle2, XCircle, Info, FileText, Cpu, Clock, Layers } from "lucide-react";

interface CheckExplanationDrawerProps {
  result: RunResult;
  testCaseName?: string;
  onClose: () => void;
}

export function CheckExplanationDrawer({
  result,
  testCaseName,
  onClose,
}: CheckExplanationDrawerProps) {
  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/50">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`flex items-center gap-1 text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                    result.status === "passed"
                      ? "bg-emerald-950/40 text-emerald-300 border-emerald-800"
                      : "bg-rose-950/40 text-rose-300 border-rose-800"
                  }`}
                >
                  {result.status === "passed" ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <XCircle className="w-3 h-3 text-rose-400" />
                  )}
                  <span className="uppercase">{result.status}</span>
                </span>
                <span className="text-xs font-mono text-slate-400">
                  Score: {(result.score ?? 0).toFixed(2)}
                </span>
              </div>
              <h3 className="text-base font-bold text-white">
                {testCaseName || `Test Case #${result.test_case_id}`}
              </h3>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Telemetry info */}
            <div className="grid grid-cols-3 gap-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
              <div>
                <span className="text-slate-500 block mb-0.5 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Latency
                </span>
                <span className="font-mono text-slate-200 font-semibold">
                  {result.latency_ms.toFixed(0)} ms
                </span>
              </div>
              <div>
                <span className="text-slate-500 block mb-0.5 flex items-center gap-1">
                  <Cpu className="w-3 h-3" /> Tokens
                </span>
                <span className="font-mono text-slate-200 font-semibold">
                  {result.total_tokens} ({result.prompt_tokens} in / {result.completion_tokens} out)
                </span>
              </div>
              <div>
                <span className="text-slate-500 block mb-0.5 flex items-center gap-1">
                  <Layers className="w-3 h-3" /> Cache
                </span>
                <span className="font-mono text-slate-200 font-semibold">
                  {result.cached ? "Hit (cached)" : "Live generation"}
                </span>
              </div>
            </div>

            {/* Regression Classification Detail */}
            {result.classification && (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-indigo-400" />
                  <span>Regression Engine Classification</span>
                </h4>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold uppercase text-indigo-300 bg-indigo-950/60 border border-indigo-800 px-2 py-0.5 rounded">
                    {result.classification}
                  </span>
                  {result.comparison_details?.reason && (
                    <span className="text-xs text-slate-300">
                      {result.comparison_details.reason}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Assertion Checks Breakdown */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-indigo-400" />
                <span>Assertion Check Results ({result.assertion_results?.length || 0})</span>
              </h4>

              {result.assertion_results && result.assertion_results.length > 0 ? (
                <div className="space-y-3">
                  {result.assertion_results.map((check, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border text-xs space-y-2 ${
                        check.passed
                          ? "bg-emerald-950/20 border-emerald-900/60"
                          : "bg-rose-950/20 border-rose-900/60"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {check.passed ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <XCircle className="w-4 h-4 text-rose-400" />
                          )}
                          <span className="font-bold text-white uppercase text-[11px] font-mono">
                            {check.type}
                          </span>
                        </div>
                        <span className="font-mono font-bold text-slate-300">
                          Score: {(check.score ?? (check.passed ? 1 : 0)).toFixed(2)}
                        </span>
                      </div>

                      <p className="text-slate-300 leading-relaxed font-medium">
                        {check.reason}
                      </p>

                      {check.details && Object.keys(check.details).length > 0 && (
                        <div className="pt-2 border-t border-slate-800/80">
                          <span className="text-[10px] text-slate-500 font-bold block mb-1">
                            Diagnostic Details:
                          </span>
                          <pre className="p-2 rounded bg-slate-950 border border-slate-800/80 font-mono text-[10px] text-slate-400 overflow-x-auto">
                            {JSON.stringify(check.details, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No assertions evaluated.</p>
              )}
            </div>

            {/* Model Output */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span>Model Output Text</span>
              </h4>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
                {result.output || (
                  <span className="text-slate-600 italic">No output produced.</span>
                )}
              </div>
            </div>

            {/* Rendered Prompt */}
            {result.rendered_prompt && (
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-400 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-slate-500" />
                  <span>Rendered Prompt Sent to Model</span>
                </h4>
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 font-mono text-[11px] text-slate-400 whitespace-pre-wrap max-h-40 overflow-y-auto">
                  {result.rendered_prompt}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
