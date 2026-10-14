"use client";

import React from "react";
import { computeLineDiff } from "@/lib/diff";
import { GitCompare, X } from "lucide-react";

interface OutputDiffViewerProps {
  testCaseName: string;
  candidateOutput: string;
  baselineOutput: string;
  onClose: () => void;
}

export function OutputDiffViewer({
  testCaseName,
  candidateOutput,
  baselineOutput,
  onClose,
}: OutputDiffViewerProps) {
  const diffLines = computeLineDiff(baselineOutput, candidateOutput);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-950/60 text-indigo-400 border border-indigo-800/80">
              <GitCompare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Output Diff</h3>
              <p className="text-xs text-slate-400">
                Comparing output for test:{" "}
                <span className="font-semibold text-slate-200">{testCaseName}</span>
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

        {/* Legend */}
        <div className="px-5 py-2.5 bg-slate-950 border-b border-slate-800/80 flex items-center gap-6 text-xs text-slate-400">
          <span className="flex items-center gap-1.5 font-medium">
            <span className="w-2.5 h-2.5 rounded bg-rose-500 inline-block" />
            <span className="text-rose-300 font-semibold">Baseline Output (Previous)</span>
          </span>
          <span className="flex items-center gap-1.5 font-medium">
            <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block" />
            <span className="text-emerald-300 font-semibold">Candidate Output (Current)</span>
          </span>
        </div>

        {/* Diff lines view */}
        <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed bg-slate-950">
          <div className="space-y-0.5">
            {diffLines.map((line, idx) => {
              if (line.type === "added") {
                return (
                  <div
                    key={idx}
                    className="flex items-start bg-emerald-950/30 text-emerald-300 px-3 py-1 rounded border-l-2 border-emerald-500"
                  >
                    <span className="w-8 select-none text-slate-600 shrink-0">
                      {line.rightLineNumber}
                    </span>
                    <span className="w-5 select-none text-emerald-500 font-bold shrink-0">
                      +
                    </span>
                    <span className="whitespace-pre-wrap break-all">{line.text}</span>
                  </div>
                );
              } else if (line.type === "removed") {
                return (
                  <div
                    key={idx}
                    className="flex items-start bg-rose-950/30 text-rose-300 px-3 py-1 rounded border-l-2 border-rose-500 line-through opacity-80"
                  >
                    <span className="w-8 select-none text-slate-600 shrink-0">
                      {line.leftLineNumber}
                    </span>
                    <span className="w-5 select-none text-rose-500 font-bold shrink-0">
                      -
                    </span>
                    <span className="whitespace-pre-wrap break-all">{line.text}</span>
                  </div>
                );
              } else {
                return (
                  <div
                    key={idx}
                    className="flex items-start text-slate-400 px-3 py-1 hover:bg-slate-900/40 rounded"
                  >
                    <span className="w-8 select-none text-slate-600 shrink-0">
                      {line.rightLineNumber}
                    </span>
                    <span className="w-5 select-none text-slate-700 shrink-0" />
                    <span className="whitespace-pre-wrap break-all">{line.text}</span>
                  </div>
                );
              }
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition"
          >
            Close Diff
          </button>
        </div>
      </div>
    </div>
  );
}
