"use client";

import React, { useState, useEffect } from "react";
import { PromptItem, PromptVersion, api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { VersionDiffDialog } from "./version-diff-dialog";
import {
  FileCode,
  GitCommit,
  GitCompare,
  Plus,
  Save,
  Clock,
  Hash,
  Variable,
  AlertCircle,
} from "lucide-react";

interface PromptEditorProps {
  projectId: number;
  prompts: PromptItem[];
  isLoading: boolean;
  onRefresh: () => void;
  onSelectPromptVersionForRun?: (versionId: number) => void;
}

export function PromptEditor({
  projectId,
  prompts,
  isLoading,
  onRefresh,
  onSelectPromptVersionForRun,
}: PromptEditorProps) {
  const { showToast } = useToast();

  const [selectedPromptId, setSelectedPromptId] = useState<number | null>(null);
  const [activeVersion, setActiveVersion] = useState<PromptVersion | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [isCommitting, setIsCommitting] = useState(false);
  const [isCreatingPrompt, setIsCreatingPrompt] = useState(false);
  const [newPromptName, setNewPromptName] = useState("");
  const [newPromptDesc, setNewPromptDesc] = useState("");

  // Diff comparison modal state
  const [diffVersionA, setDiffVersionA] = useState<PromptVersion | null>(null);
  const [diffVersionB, setDiffVersionB] = useState<PromptVersion | null>(null);

  // Initialize selected prompt
  useEffect(() => {
    if (prompts.length > 0 && !selectedPromptId) {
      setSelectedPromptId(prompts[0].id);
    }
  }, [prompts, selectedPromptId]);

  const activePrompt = prompts.find((p) => p.id === selectedPromptId);
  const versions = activePrompt?.versions || [];

  // Update active version and editor content when activePrompt or its versions change
  useEffect(() => {
    if (versions.length > 0) {
      const latest = versions[0];
      setActiveVersion(latest);
      setEditorContent(latest.content);
    } else {
      setActiveVersion(null);
      setEditorContent("");
    }
  }, [selectedPromptId, activePrompt]);

  // Extract Jinja2 input variables automatically from editor content
  const detectedVariables = Array.from(
    new Set(
      Array.from(editorContent.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)).map(
        (m) => m[1]
      )
    )
  );

  const handleSelectVersion = (version: PromptVersion) => {
    setActiveVersion(version);
    setEditorContent(version.content);
  };

  const handleSaveVersion = async () => {
    if (!selectedPromptId || !editorContent.trim()) return;

    setIsCommitting(true);
    try {
      const v = await api.createPromptVersion(selectedPromptId, {
        content: editorContent,
        commit_message: commitMessage.trim() || undefined,
      });
      showToast(`Prompt version v${v.version_number} committed!`, "success");
      setCommitMessage("");
      onRefresh();
    } catch (err: any) {
      showToast(err.message || "Failed to commit prompt version", "error");
    } finally {
      setIsCommitting(false);
    }
  };

  const handleCreatePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPromptName.trim()) return;

    try {
      const p = await api.createPrompt(projectId, {
        name: newPromptName.trim(),
        description: newPromptDesc.trim() || undefined,
        initial_version_content: "Hello {{ name }}, your query is: {{ query }}",
        commit_message: "v1.0.0: Initial prompt version",
      });
      showToast(`Prompt "${p.name}" created!`, "success");
      setIsCreatingPrompt(false);
      setNewPromptName("");
      setNewPromptDesc("");
      onRefresh();
      setSelectedPromptId(p.id);
    } catch (err: any) {
      showToast(err.message || "Failed to create prompt", "error");
    }
  };

  if (isLoading) {
    return (
      <div className="h-96 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse p-6" />
    );
  }

  if (prompts.length === 0) {
    return (
      <div className="text-center py-16 px-4 rounded-3xl bg-slate-900/40 border border-dashed border-slate-800 max-w-xl mx-auto my-8">
        <FileCode className="w-12 h-12 text-slate-500 mx-auto mb-3" />
        <h3 className="text-base font-bold text-white mb-1">No Prompts Created</h3>
        <p className="text-xs text-slate-400 max-w-sm mx-auto mb-6">
          Create a prompt template with Jinja2 placeholders (e.g. {"{{ user_query }}"}) to begin evaluating.
        </p>
        <button
          onClick={() => setIsCreatingPrompt(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg transition"
        >
          <Plus className="w-4 h-4" />
          <span>Create First Prompt</span>
        </button>
      </div>
    );
  }

  const isContentModified = activeVersion && editorContent !== activeVersion.content;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Prompt Selector Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-400">Prompt:</label>
          <select
            value={selectedPromptId || ""}
            onChange={(e) => setSelectedPromptId(Number(e.target.value))}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {prompts.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>

          <button
            onClick={() => setIsCreatingPrompt(true)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-800 border border-slate-700 transition"
            title="Create another prompt"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Action button to select for run */}
        {activeVersion && onSelectPromptVersionForRun && (
          <button
            onClick={() => onSelectPromptVersionForRun(activeVersion.id)}
            className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-indigo-300 bg-indigo-950/60 hover:bg-indigo-950/90 border border-indigo-800/80 rounded-xl transition"
          >
            <span>Run Tests with v{activeVersion.version_number}</span>
          </button>
        )}
      </div>

      {/* Main Grid: Editor on Left, Version History on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Editor Area (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-5 shadow-xl flex flex-col h-[520px]">
            {/* Editor Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-indigo-400" />
                <span className="text-xs font-bold text-slate-200">
                  Jinja2 Template Editor
                </span>
                {isContentModified && (
                  <span className="text-[10px] font-semibold text-amber-400 bg-amber-950/40 border border-amber-800/80 px-2 py-0.5 rounded-full">
                    Unsaved changes
                  </span>
                )}
              </div>

              {activeVersion && (
                <span className="text-xs font-mono text-slate-500">
                  Viewing: v{activeVersion.version_number}
                </span>
              )}
            </div>

            {/* Code / Text Area */}
            <textarea
              value={editorContent}
              onChange={(e) => setEditorContent(e.target.value)}
              placeholder="Enter your prompt template with {{ variable }} placeholders..."
              className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs sm:text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 leading-relaxed resize-none"
            />

            {/* Detected Variables Footer */}
            <div className="pt-3 mt-3 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <Variable className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-slate-400">Detected Inputs:</span>
                {detectedVariables.length === 0 ? (
                  <span className="text-slate-600 italic">None</span>
                ) : (
                  detectedVariables.map((v) => (
                    <span
                      key={v}
                      className="px-2 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800 text-[11px] font-mono"
                    >
                      {v}
                    </span>
                  ))
                )}
              </div>

              <span className="text-slate-500 text-[11px]">
                {editorContent.length} chars
              </span>
            </div>
          </div>

          {/* Commit Bar */}
          <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row items-center gap-3">
            <input
              type="text"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              placeholder="Commit message (e.g. 'Add clarification for order refunds')..."
              className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={handleSaveVersion}
              disabled={isCommitting || !editorContent.trim() || !isContentModified}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition disabled:opacity-40"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{isCommitting ? "Committing..." : "Commit New Version"}</span>
            </button>
          </div>
        </div>

        {/* Version History Sidebar (1 col) */}
        <div className="space-y-4">
          <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-5 shadow-xl flex flex-col h-[590px]">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2">
                <GitCommit className="w-4 h-4 text-indigo-400" />
                <h4 className="text-xs font-bold text-slate-200">
                  Immutable Versions ({versions.length})
                </h4>
              </div>
            </div>

            <div className="flex-1 overflow-auto space-y-2.5 pr-1">
              {versions.map((ver, idx) => {
                const isSelected = activeVersion?.id === ver.id;
                const prevVer = versions[idx + 1];

                return (
                  <div
                    key={ver.id}
                    onClick={() => handleSelectVersion(ver)}
                    className={`p-3.5 rounded-xl border text-xs cursor-pointer transition ${
                      isSelected
                        ? "bg-indigo-950/40 border-indigo-500/80 shadow-md shadow-indigo-500/10"
                        : "bg-slate-950/60 hover:bg-slate-950 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-xs">
                          v{ver.version_number}
                        </span>
                        {idx === 0 && (
                          <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-950/40 border border-emerald-800 px-1.5 py-0.2 rounded">
                            Latest
                          </span>
                        )}
                      </div>

                      {prevVer && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDiffVersionA(prevVer);
                            setDiffVersionB(ver);
                          }}
                          className="flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-indigo-300 p-1 hover:bg-slate-800 rounded transition"
                          title="View diff against previous version"
                        >
                          <GitCompare className="w-3 h-3" />
                          <span>Diff</span>
                        </button>
                      )}
                    </div>

                    <p className="text-[11px] text-slate-300 line-clamp-2 mb-2 font-medium">
                      {ver.commit_message || "No commit message provided"}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1.5 border-t border-slate-800/80 font-mono">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(ver.created_at).toLocaleDateString()}</span>
                      </span>
                      <span className="flex items-center gap-0.5 truncate max-w-[90px]">
                        <Hash className="w-3 h-3 text-slate-600" />
                        <span>{ver.content_hash.slice(0, 8)}</span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* New Prompt Modal */}
      {isCreatingPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <h3 className="text-base font-bold text-white mb-1">Create New Prompt</h3>
            <p className="text-xs text-slate-400 mb-4">
              Add another prompt template to this project suite.
            </p>

            <form onSubmit={handleCreatePrompt} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Prompt Name *
                </label>
                <input
                  type="text"
                  required
                  value={newPromptName}
                  onChange={(e) => setNewPromptName(e.target.value)}
                  placeholder="e.g. Sentiment Analyzer"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={newPromptDesc}
                  onChange={(e) => setNewPromptDesc(e.target.value)}
                  placeholder="Purpose of this prompt..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCreatingPrompt(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg transition"
                >
                  Create Prompt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Version Diff Dialog */}
      {diffVersionA && diffVersionB && (
        <VersionDiffDialog
          versionA={diffVersionA}
          versionB={diffVersionB}
          onClose={() => {
            setDiffVersionA(null);
            setDiffVersionB(null);
          }}
        />
      )}
    </div>
  );
}
