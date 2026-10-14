"use client";

import React, { useState } from "react";
import { Project, PromptItem, TestCase, Run } from "@/lib/api";
import { PromptEditor } from "@/components/prompts/prompt-editor";
import { TestTable } from "@/components/tests/test-table";
import { RunHistoryChart } from "@/components/runs/run-history-chart";
import { RunReport } from "@/components/runs/run-report";
import { LiveRunProgress } from "@/components/runs/live-run-progress";
import { RunConfirmationDialog } from "@/components/runs/run-confirmation-dialog";
import { ApiKeySettings } from "@/components/settings/api-key-settings";
import {
  FileCode,
  ListChecks,
  History,
  Settings,
  Play,
  ArrowLeft,
  KeyRound,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

interface ProjectDashboardProps {
  project: Project;
  prompts: PromptItem[];
  testCases: TestCase[];
  runs: Run[];
  isLoading: boolean;
  activeTab?: "prompts" | "tests" | "runs" | "settings";
  onTabChange?: (tab: "prompts" | "tests" | "runs" | "settings") => void;
  onRefresh: () => void;
  onBackToProjects: () => void;
}

export function ProjectDashboard({
  project,
  prompts,
  testCases,
  runs,
  isLoading,
  activeTab: controlledTab,
  onTabChange,
  onRefresh,
  onBackToProjects,
}: ProjectDashboardProps) {
  const [internalTab, setInternalTab] = useState<"prompts" | "tests" | "runs" | "settings">("prompts");
  const activeTab = controlledTab ?? internalTab;
  const setActiveTab = onTabChange ?? setInternalTab;
  const [activeRunReport, setActiveRunReport] = useState<Run | null>(null);
  const [liveRun, setLiveRun] = useState<Run | null>(null);
  const [isRunDialogOpen, setIsRunDialogOpen] = useState(false);
  const [selectedPromptVersionId, setSelectedPromptVersionId] = useState<number | null>(null);

  // If activeRunReport is selected, find its baseline run
  const baselineRun = activeRunReport?.baseline_run_id
    ? runs.find((r) => r.id === activeRunReport.baseline_run_id) || null
    : null;

  const handleStartRunFromPrompt = (versionId: number) => {
    setSelectedPromptVersionId(versionId);
    setIsRunDialogOpen(true);
  };

  const handleRunCreated = (newRun: Run) => {
    setLiveRun(newRun);
    setActiveTab("runs");
    onRefresh();
  };

  const handleLiveRunCompleted = (completedRun: Run) => {
    setLiveRun(null);
    setActiveRunReport(completedRun);
    onRefresh();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 animate-in fade-in duration-300">
      {/* Project Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="space-y-1">
          <button
            onClick={onBackToProjects}
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white transition mb-2"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>All Projects</span>
          </button>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            {project.name}
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 max-w-2xl">
            {project.description || "Prompt regression test suite and evaluator framework."}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {!project.has_api_key && (
            <button
              onClick={() => setActiveTab("settings")}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-800 animate-pulse hover:bg-amber-950/90 transition"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>Configure Gemini Key</span>
            </button>
          )}

          <button
            onClick={() => setIsRunDialogOpen(true)}
            className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>Run Evaluation</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 text-sm font-semibold">
        <button
          onClick={() => {
            setActiveTab("prompts");
            setActiveRunReport(null);
          }}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 -mb-px transition ${
            activeTab === "prompts" && !activeRunReport
              ? "border-indigo-500 text-white"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <FileCode className="w-4 h-4 text-indigo-400" />
          <span>Prompts & Versions</span>
        </button>

        <button
          onClick={() => {
            setActiveTab("tests");
            setActiveRunReport(null);
          }}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 -mb-px transition ${
            activeTab === "tests"
              ? "border-indigo-500 text-white"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <ListChecks className="w-4 h-4 text-cyan-400" />
          <span>Test Cases & Checks ({testCases.filter((t) => t.is_active).length})</span>
        </button>

        <button
          onClick={() => {
            setActiveTab("runs");
            setActiveRunReport(null);
          }}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 -mb-px transition ${
            activeTab === "runs"
              ? "border-indigo-500 text-white"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <History className="w-4 h-4 text-emerald-400" />
          <span>Runs & Regressions ({runs.length})</span>
        </button>

        <button
          onClick={() => {
            setActiveTab("settings");
            setActiveRunReport(null);
          }}
          className={`flex items-center gap-2 px-4 py-3 border-b-2 -mb-px transition ${
            activeTab === "settings"
              ? "border-indigo-500 text-white"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Settings className="w-4 h-4 text-slate-400" />
          <span>Settings</span>
        </button>
      </div>

      {/* Live Running Progress Tracker (if active) */}
      {liveRun && (
        <LiveRunProgress
          run={liveRun}
          onCompleted={handleLiveRunCompleted}
          onCancelled={() => setLiveRun(null)}
        />
      )}

      {/* Tab Panels */}
      {activeTab === "prompts" && (
        <PromptEditor
          projectId={project.id}
          prompts={prompts}
          isLoading={isLoading}
          onRefresh={onRefresh}
          onSelectPromptVersionForRun={handleStartRunFromPrompt}
        />
      )}

      {activeTab === "tests" && (
        <TestTable
          projectId={project.id}
          testCases={testCases}
          isLoading={isLoading}
          onRefresh={onRefresh}
        />
      )}

      {activeTab === "runs" && (
        <>
          {activeRunReport ? (
            <RunReport
              run={activeRunReport}
              baselineRun={baselineRun}
              onRefresh={onRefresh}
              onBackToRunsList={() => setActiveRunReport(null)}
            />
          ) : (
            <RunHistoryChart
              runs={runs}
              onSelectRun={(r) => setActiveRunReport(r)}
              onStartNewRun={() => setIsRunDialogOpen(true)}
            />
          )}
        </>
      )}

      {activeTab === "settings" && (
        <ApiKeySettings project={project} onRefresh={onRefresh} />
      )}

      {/* Run Confirmation Dialog */}
      {isRunDialogOpen && (
        <RunConfirmationDialog
          projectId={project.id}
          prompts={prompts}
          runs={runs}
          activeVersionId={selectedPromptVersionId}
          totalActiveTests={testCases.filter((t) => t.is_active).length}
          hasApiKey={project.has_api_key}
          onClose={() => setIsRunDialogOpen(false)}
          onRunCreated={handleRunCreated}
          onOpenSettings={() => setActiveTab("settings")}
        />
      )}
    </div>
  );
}
