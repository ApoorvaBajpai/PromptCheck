"use client";

import React from "react";
import { PromptVersion } from "@/lib/api";
import { computeLineDiff } from "@/lib/diff";
import { GitCompare, X } from "lucide-react";

interface VersionDiffDialogProps {
  versionA: PromptVersion;
  versionB: PromptVersion;
  onClose: () => void;
}

export function VersionDiffDialog({
  versionA,
  versionB,
  onClose,
}: VersionDiffDialogProps) {
  const diffLines = computeLineDiff(versionA.content, versionB.content);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-950/60 text-indigo-400 border border-indigo-800/80">
              <GitCompare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Prompt Version Diff</h3>
              <p className="text-xs text-slate-400">
                Comparing{" "}
                <span className="font-semibold text-rose-400">v{versionA.version_number}</span>{" "}
                with{" "}
                <span className="font-semibold text-emerald-400">v{versionB.version_number}</span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Diff Content */}
        <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed bg-slate-950">
          {diffLines.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              No content differences found between these versions.
            </div>
          ) : (
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
                      className="flex items-start text-slate-400 px-3 py-1 hover:bg-slate-900/50 rounded"
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
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/50 flex justify-between items-center text-xs text-slate-400">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-emerald-500 inline-block" />
              <span>Added lines</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded bg-rose-500 inline-block" />
              <span>Removed lines</span>
            </span>
          </div>

          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 rounded-xl transition"
          >
            Close Diff
          </button>
        </div>
      </div>
    </div>
  );
}
