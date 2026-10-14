"use client";

import React, { useState } from "react";
import { Project, api } from "@/lib/api";
import { loadExampleProject } from "@/lib/example-project";
import { useToast } from "@/components/providers";
import {
  FolderKanban,
  Plus,
  Sparkles,
  KeyRound,
  CheckCircle2,
  AlertTriangle,
  Search,
  ArrowRight,
  Trash2,
  Clock,
} from "lucide-react";

interface ProjectListProps {
  projects: Project[];
  isLoading: boolean;
  onSelectProject: (project: Project) => void;
  onRefresh: () => void;
}

export function ProjectList({
  projects,
  isLoading,
  onSelectProject,
  onRefresh,
}: ProjectListProps) {
  const { showToast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDesc, setNewProjectDesc] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");

  const filtered = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.description && p.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;

    try {
      const proj = await api.createProject({
        name: newProjectName.trim(),
        description: newProjectDesc.trim() || undefined,
        gemini_api_key: apiKeyInput.trim() || undefined,
      });
      showToast(`Created project "${proj.name}"`, "success");
      setIsCreating(false);
      setNewProjectName("");
      setNewProjectDesc("");
      setApiKeyInput("");
      onRefresh();
      onSelectProject(proj);
    } catch (err: any) {
      showToast(err.message || "Failed to create project", "error");
    }
  };

  const handleLoadExample = async () => {
    setIsSeeding(true);
    try {
      const proj = await loadExampleProject();
      showToast("Example QA Bot project with 10 test cases loaded!", "success");
      onRefresh();
      onSelectProject(proj);
    } catch (err: any) {
      showToast(err.message || "Failed to load example project", "error");
    } finally {
      setIsSeeding(false);
    }
  };

  const handleDelete = async (projectId: number, projectName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete project "${projectName}"?`)) return;

    try {
      await api.deleteProject(projectId);
      showToast(`Project "${projectName}" deleted`, "info");
      onRefresh();
    } catch (err: any) {
      showToast(err.message || "Failed to delete project", "error");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-in fade-in duration-300">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <FolderKanban className="w-8 h-8 text-indigo-400" />
            <span>Prompt Projects</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Select an evaluation suite to test prompt versions, inspect regressions, and run checks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleLoadExample}
            disabled={isSeeding}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-amber-300 bg-amber-950/40 hover:bg-amber-950/70 border border-amber-800/80 rounded-xl transition disabled:opacity-50"
            title="Preload Customer Support QA Bot with 10 tests"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>{isSeeding ? "Seeding..." : "Load Example Project (QA Bot)"}</span>
          </button>

          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition"
          >
            <Plus className="w-4 h-4" />
            <span>New Project</span>
          </button>
        </div>
      </div>

      {/* Search Bar */}
      {projects.length > 0 && (
        <div className="mt-6 mb-6">
          <div className="relative max-w-md">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search projects..."
              className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-44 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse p-6"
            />
          ))}
        </div>
      ) : projects.length === 0 ? (
        /* Empty State */
        <div className="mt-12 text-center py-16 px-4 rounded-3xl bg-slate-900/40 border border-dashed border-slate-800 max-w-2xl mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-indigo-950/80 border border-indigo-800/80 text-indigo-400 mx-auto flex items-center justify-center mb-4">
            <FolderKanban className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-white mb-2">No Projects Yet</h3>
          <p className="text-sm text-slate-400 max-w-md mx-auto mb-6">
            Get started by creating your first prompt evaluation project or load our pre-configured QA Bot example suite.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={handleLoadExample}
              disabled={isSeeding}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-amber-200 bg-amber-950/60 hover:bg-amber-950/90 border border-amber-800 rounded-xl transition"
            >
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>{isSeeding ? "Loading..." : "Load Example Project: QA Bot"}</span>
            </button>
            <button
              onClick={() => setIsCreating(true)}
              className="flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition"
            >
              <Plus className="w-4 h-4" />
              <span>Create New Project</span>
            </button>
          </div>
        </div>
      ) : (
        /* Projects Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
          {filtered.map((proj) => (
            <div
              key={proj.id}
              onClick={() => onSelectProject(proj)}
              className="group relative cursor-pointer rounded-2xl bg-slate-900/80 hover:bg-slate-900 border border-slate-800 hover:border-indigo-500/50 p-6 transition-all duration-200 shadow-xl hover:shadow-indigo-500/10 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition truncate">
                    {proj.name}
                  </h3>
                  <button
                    onClick={(e) => handleDelete(proj.id, proj.name, e)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition"
                    title="Delete Project"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <p className="text-xs text-slate-400 line-clamp-2 mb-4 leading-relaxed">
                  {proj.description || "No description provided."}
                </p>
              </div>

              <div className="pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  {proj.has_api_key ? (
                    <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/40 border border-emerald-800/80 px-2 py-0.5 rounded-full">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>API Key Set</span>
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-950/40 border border-amber-800/80 px-2 py-0.5 rounded-full">
                      <AlertTriangle className="w-3 h-3" />
                      <span>No API Key</span>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1 text-indigo-400 group-hover:translate-x-1 transition font-medium">
                  <span>Open</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      {isCreating && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl animate-in zoom-in-95 duration-150">
            <h3 className="text-lg font-bold text-white mb-1">Create Evaluation Project</h3>
            <p className="text-xs text-slate-400 mb-5">
              Set up a new space for your prompt versions, assertions, and runs.
            </p>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Project Name *
                </label>
                <input
                  type="text"
                  required
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="e.g. Legal Doc Analyzer"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Description (optional)
                </label>
                <textarea
                  rows={3}
                  value={newProjectDesc}
                  onChange={(e) => setNewProjectDesc(e.target.value)}
                  placeholder="What is this prompt evaluation project for?"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
                  <span>Gemini API Key (optional)</span>
                  <span className="text-[10px] text-emerald-400 font-mono">Encrypted at rest</span>
                </label>
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder="AIzaSy... (leave blank to configure later)"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
