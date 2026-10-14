"use client";

import React, { useState } from "react";
import { Run, RunResult, api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { OutputDiffViewer } from "./output-diff-viewer";
import { CheckExplanationDrawer } from "./check-explanation-drawer";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  MinusCircle,
  HelpCircle,
  Cpu,
  Clock,
  Pin,
  GitCompare,
  Eye,
  ArrowRight,
  Filter,
} from "lucide-react";

interface RunReportProps {
  run: Run;
  baselineRun?: Run | null;
  onRefresh: () => void;
  onBackToRunsList?: () => void;
}

export function RunReport({
  run,
  baselineRun,
  onRefresh,
  onBackToRunsList,
}: RunReportProps) {
  const { showToast } = useToast();

  const [activeTab, setActiveTab] = useState<
    "all" | "regression" | "soft_regression" | "improvement" | "unchanged"
  >("all");

  const [inspectingResult, setInspectingResult] = useState<RunResult | null>(null);
  const [diffingResult, setDiffingResult] = useState<{
    result: RunResult;
    baselineResultText: string;
  } | null>(null);

  const [isDesignatingBaseline, setIsDesignatingBaseline] = useState(false);

  const results = run.results || [];
  const summary = run.summary;
  const hasBaseline = Boolean(run.baseline_run_id);

  // Categorize results accurately whether a baseline exists or not
  const regressions = results.filter(
    (r) => r.classification === "regression" || (!hasBaseline && r.status === "failed")
  );
  const softRegressions = results.filter(
    (r) => r.classification === "soft_regression"
  );
  const improvements = results.filter(
    (r) => r.classification === "improvement"
  );
  const unchanged = results.filter(
    (r) =>
      r.classification === "unchanged" ||
      r.classification === "passed" ||
      (!hasBaseline && r.status === "passed") ||
      (r.status === "passed" && !r.classification)
  );
  const inconclusive = results.filter(
    (r) =>
      r.classification === "inconclusive" ||
      r.status === "error" ||
      (![...regressions, ...softRegressions, ...improvements, ...unchanged].includes(r))
  );

  // Sort with regressions/failed tests first for maximum visibility
  const sortedAllResults = [...results].sort((a, b) => {
    const scoreA =
      a.classification === "regression" || a.status === "failed" ? 0 : 1;
    const scoreB =
      b.classification === "regression" || b.status === "failed" ? 0 : 1;
    return scoreA - scoreB;
  });

  // Filter based on active tab
  const displayedResults =
    activeTab === "all"
      ? sortedAllResults
      : activeTab === "regression"
      ? regressions
      : activeTab === "soft_regression"
      ? softRegressions
      : activeTab === "improvement"
      ? improvements
      : unchanged;

  const handleSetProjectBaseline = async () => {
    setIsDesignatingBaseline(true);
    try {
      await api.setRunBaseline(run.id, { set_as_project_baseline: true });
      showToast(`Run #${run.id} designated as Project Baseline!`, "success");
      onRefresh();
    } catch (err: any) {
      showToast(err.message || "Failed to set baseline", "error");
    } finally {
      setIsDesignatingBaseline(false);
    }
  };

  const handleOpenDiff = (r: RunResult) => {
    // If baseline run exists, find matching test case output
    const baseMatch = baselineRun?.results?.find(
      (br) => br.test_case_id === r.test_case_id
    );
    const baselineText = baseMatch?.output || "No prior baseline output available.";
    setDiffingResult({ result: r, baselineResultText: baselineText });
  };

  // Determine Executive Verdict (<10 second comprehension)
  const hasHardRegressions =
    hasBaseline &&
    ((summary?.regressions ?? 0) > 0 ||
      results.some((r) => r.classification === "regression"));
  const hasSoftRegressions =
    hasBaseline &&
    ((summary?.soft_regressions ?? 0) > 0 ||
      results.some((r) => r.classification === "soft_regression"));
  const isAllPassed = run.failed_tests === 0;

  // Latency & duration calculation
  const runDurationSec =
    run.started_at && run.completed_at
      ? Math.max(
          0,
          (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) /
            1000
        )
      : null;
  const cumulativeLatencySec =
    results.reduce((acc, r) => acc + (r.latency_ms || 0), 0) / 1000;
  const isAllCached = results.length > 0 && results.every((r) => r.cached);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* 1. EXECUTIVE 10-SECOND VERDICT BANNER (Never color alone; icons + text) */}
      <div
        className={`p-6 sm:p-7 rounded-3xl border shadow-2xl relative overflow-hidden ${
          hasHardRegressions
            ? "bg-gradient-to-r from-rose-950/80 via-rose-900/40 to-slate-900 border-rose-700/80"
            : hasSoftRegressions
            ? "bg-gradient-to-r from-amber-950/80 via-amber-900/40 to-slate-900 border-amber-700/80"
            : !hasBaseline && !isAllPassed
            ? "bg-gradient-to-r from-amber-950/70 via-slate-900 to-slate-900 border-amber-700/60"
            : isAllPassed
            ? "bg-gradient-to-r from-emerald-950/80 via-emerald-900/40 to-slate-900 border-emerald-700/80"
            : "bg-slate-900 border-slate-800"
        }`}
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="flex items-start sm:items-center gap-4">
            <div
              className={`p-3.5 rounded-2xl shadow-xl shrink-0 ${
                hasHardRegressions
                  ? "bg-rose-600 text-white"
                  : hasSoftRegressions || (!hasBaseline && !isAllPassed)
                  ? "bg-amber-500 text-slate-950"
                  : "bg-emerald-500 text-slate-950"
              }`}
            >
              {hasHardRegressions ? (
                <AlertOctagon className="w-8 h-8" />
              ) : hasSoftRegressions || (!hasBaseline && !isAllPassed) ? (
                <AlertTriangle className="w-8 h-8" />
              ) : (
                <CheckCircle2 className="w-8 h-8" />
              )}
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="text-xs uppercase font-extrabold tracking-wider px-2.5 py-0.5 rounded-full bg-slate-950/70 text-slate-200 border border-slate-800">
                  Run #{run.id} • Evaluation Report
                </span>
                {run.baseline_run_id ? (
                  <span className="text-xs text-indigo-300 font-semibold bg-indigo-950/60 px-2 py-0.5 rounded-md border border-indigo-800/60">
                    Compared against Baseline Run #{run.baseline_run_id}
                  </span>
                ) : (
                  <span className="text-xs text-slate-400 font-medium">
                    Initial Run (No baseline set)
                  </span>
                )}
              </div>

              <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                {hasHardRegressions
                  ? "❌ REGRESSION DETECTED"
                  : hasSoftRegressions
                  ? "⚠️ SOFT REGRESSION DETECTED"
                  : !hasBaseline && !isAllPassed
                  ? "⚠️ EVALUATION COMPLETED WITH FAILURES"
                  : isAllPassed
                  ? "🟢 ALL EVALUATION CHECKS PASSED"
                  : "EVALUATION COMPLETED"}
              </h2>

              <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
                {hasHardRegressions
                  ? `${regressions.length} test case(s) that previously passed are now failing on this prompt version. Inspect regressions below.`
                  : hasSoftRegressions
                  ? "Tests passed assertions, but semantic similarity scores or pass rates dropped compared to the baseline."
                  : !hasBaseline && !isAllPassed
                  ? `${run.failed_tests} of ${run.total_tests} tests failed on this prompt version. Review the check results below or designate a baseline to track regressions.`
                  : !hasBaseline && isAllPassed
                  ? `All ${run.total_tests} tests passed! Set this run as Project Baseline to track regression trends across future prompt versions.`
                  : "No regressions detected compared to baseline. All checks passed successfully."}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSetProjectBaseline}
              disabled={isDesignatingBaseline || run.status !== "completed"}
              className="flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:text-white bg-slate-950/80 hover:bg-slate-950 border border-slate-700 rounded-xl transition"
              title="Designate this run as the permanent benchmark for future runs"
            >
              <Pin className="w-3.5 h-3.5 text-indigo-400" />
              <span>
                {isDesignatingBaseline ? "Setting..." : "Set as Project Baseline"}
              </span>
            </button>

            {onBackToRunsList && (
              <button
                onClick={onBackToRunsList}
                className="px-4 py-2.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition"
              >
                Back to Runs
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 2. SUMMARY METRICS ROW */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <span className="text-[11px] font-bold text-slate-400 block mb-1">
            Pass Rate
          </span>
          <div className="text-xl font-extrabold text-white font-mono">
            {run.total_tests > 0
              ? `${Math.round((run.passed_tests / run.total_tests) * 100)}%`
              : "0%"}
          </div>
          <span className="text-[10px] text-slate-500">
            {run.passed_tests} / {run.total_tests} tests
          </span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <span className="text-[11px] font-bold text-slate-400 block mb-1 flex items-center gap-1">
            <AlertOctagon className="w-3 h-3 text-rose-400" />
            <span>{hasBaseline ? "Regressions" : "Failures"}</span>
          </span>
          <div
            className={`text-xl font-extrabold font-mono ${
              regressions.length > 0 ? "text-rose-400" : "text-white"
            }`}
          >
            {hasBaseline ? (summary?.regressions ?? regressions.length) : run.failed_tests}
          </div>
          <span className="text-[10px] text-slate-500">
            {hasBaseline ? "Hard pass → fail" : "Failed tests"}
          </span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <span className="text-[11px] font-bold text-slate-400 block mb-1 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 text-amber-400" />
            <span>Soft Regressions</span>
          </span>
          <div
            className={`text-xl font-extrabold font-mono ${
              softRegressions.length > 0 ? "text-amber-400" : "text-white"
            }`}
          >
            {summary?.soft_regressions ?? softRegressions.length}
          </div>
          <span className="text-[10px] text-slate-500">Score drop ≥ 15%</span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <span className="text-[11px] font-bold text-slate-400 block mb-1 flex items-center gap-1">
            <TrendingUp className="w-3 h-3 text-emerald-400" />
            <span>Improvements</span>
          </span>
          <div className="text-xl font-extrabold text-emerald-400 font-mono">
            {summary?.improvements ?? improvements.length}
          </div>
          <span className="text-[10px] text-slate-500">Fail → pass</span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <span className="text-[11px] font-bold text-slate-400 block mb-1 flex items-center gap-1">
            <Clock className="w-3 h-3 text-cyan-400" />
            <span>Total Latency</span>
          </span>
          <div className="text-xl font-extrabold text-white font-mono">
            {cumulativeLatencySec > 0
              ? `${cumulativeLatencySec.toFixed(1)}s`
              : runDurationSec !== null
              ? `${runDurationSec.toFixed(1)}s`
              : "0.0s"}
          </div>
          <span className="text-[10px] text-slate-500">
            {isAllCached ? "Cached run time" : "Cumulative time"}
          </span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800">
          <span className="text-[11px] font-bold text-slate-400 block mb-1 flex items-center gap-1">
            <Cpu className="w-3 h-3 text-indigo-400" />
            <span>Total Tokens</span>
          </span>
          <div className="text-xl font-extrabold text-white font-mono">
            {results.reduce((acc, r) => acc + (r.total_tokens || 0), 0)}
          </div>
          <span className="text-[10px] text-slate-500">Prompt + completion</span>
        </div>
      </div>

      {/* 3. TEST RESULTS BREAKDOWN (SHOW REGRESSIONS FIRST) */}
      <div className="space-y-4">
        {/* Filter Tabs Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-400">Filter View:</span>
            <div className="flex border border-slate-800 rounded-xl p-0.5 bg-slate-950 text-xs font-semibold">
              <button
                onClick={() => setActiveTab("all")}
                className={`px-3 py-1 rounded-lg transition ${
                  activeTab === "all"
                    ? "bg-indigo-600 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                All Tests ({results.length})
              </button>
              <button
                onClick={() => setActiveTab("regression")}
                className={`px-3 py-1 rounded-lg transition flex items-center gap-1.5 ${
                  activeTab === "regression"
                    ? "bg-rose-600 text-white"
                    : "text-rose-400 hover:text-rose-300"
                }`}
              >
                <AlertOctagon className="w-3.5 h-3.5" />
                <span>
                  {hasBaseline
                    ? `Regressions (${regressions.length})`
                    : `Failed (${run.failed_tests})`}
                </span>
              </button>
              <button
                onClick={() => setActiveTab("soft_regression")}
                className={`px-3 py-1 rounded-lg transition flex items-center gap-1.5 ${
                  activeTab === "soft_regression"
                    ? "bg-amber-600 text-white"
                    : "text-amber-400 hover:text-amber-300"
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Soft Regressions ({softRegressions.length})</span>
              </button>
              <button
                onClick={() => setActiveTab("improvement")}
                className={`px-3 py-1 rounded-lg transition flex items-center gap-1.5 ${
                  activeTab === "improvement"
                    ? "bg-emerald-600 text-white"
                    : "text-emerald-400 hover:text-emerald-300"
                }`}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Improvements ({improvements.length})</span>
              </button>
              <button
                onClick={() => setActiveTab("unchanged")}
                className={`px-3 py-1 rounded-lg transition ${
                  activeTab === "unchanged"
                    ? "bg-slate-700 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {hasBaseline
                  ? `Unchanged (${unchanged.length})`
                  : `Passed (${unchanged.length})`}
              </button>
            </div>
          </div>
        </div>

        {/* Results List */}
        <div className="space-y-3">
          {displayedResults.map((r) => {
            const isReg = r.classification === "regression" || r.status === "failed";
            const isSoft = r.classification === "soft_regression";
            const isImp = r.classification === "improvement";

            return (
              <div
                key={r.id}
                className={`p-4 sm:p-5 rounded-2xl border transition-all ${
                  isReg
                    ? "bg-rose-950/20 border-rose-900/80 shadow-lg shadow-rose-950/20"
                    : isSoft
                    ? "bg-amber-950/20 border-amber-900/80 shadow-lg shadow-amber-950/20"
                    : isImp
                    ? "bg-emerald-950/15 border-emerald-900/60"
                    : "bg-slate-900/80 border-slate-800"
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  {/* Test Info */}
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Classification Badge (Never color alone; icons + text) */}
                      {isReg ? (
                        <span className="flex items-center gap-1 text-[11px] font-bold text-rose-300 bg-rose-950/80 border border-rose-700 px-2.5 py-0.5 rounded-full">
                          <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
                          <span>
                            {hasBaseline && r.classification === "regression"
                              ? "❌ Hard Regression"
                              : "❌ Test Failed"}
                          </span>
                        </span>
                      ) : isSoft ? (
                        <span className="flex items-center gap-1 text-[11px] font-bold text-amber-300 bg-amber-950/80 border border-amber-700 px-2.5 py-0.5 rounded-full">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                          <span>⚠️ Soft Regression</span>
                        </span>
                      ) : isImp ? (
                        <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-300 bg-emerald-950/80 border border-emerald-700 px-2.5 py-0.5 rounded-full">
                          <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                          <span>🟢 Improvement</span>
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[11px] font-bold text-emerald-300 bg-emerald-950/60 border border-emerald-800/80 px-2.5 py-0.5 rounded-full">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>
                            {hasBaseline && r.classification === "unchanged"
                              ? "⚪ Unchanged"
                              : "✅ Test Passed"}
                          </span>
                        </span>
                      )}

                      <span className="text-sm font-bold text-white">
                        Test #{r.test_case_id}
                      </span>

                      <span className="text-xs font-mono text-slate-400">
                        Score: {(r.score ?? 0).toFixed(2)}
                      </span>
                    </div>

                    {/* Reason explanation */}
                    <p className="text-xs text-slate-300 leading-relaxed font-medium">
                      {r.comparison_details?.reason ||
                        r.error_message ||
                        "Evaluation passed all configured assertion checks."}
                    </p>

                    {/* Output snippet */}
                    {r.output && (
                      <p className="text-xs font-mono text-slate-400 line-clamp-1 bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
                        {r.output}
                      </p>
                    )}
                  </div>

                  {/* Actions: View Explanations / Side-by-side Output Diff */}
                  <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                    <button
                      onClick={() => handleOpenDiff(r)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-950 hover:bg-slate-800 border border-slate-800 rounded-xl transition"
                      title="Compare candidate output vs baseline output"
                    >
                      <GitCompare className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Compare Diff</span>
                    </button>

                    <button
                      onClick={() => setInspectingResult(r)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600/80 hover:bg-indigo-600 border border-indigo-500 rounded-xl transition shadow"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Inspect Checks</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Inspect Check Explanations Drawer */}
      {inspectingResult && (
        <CheckExplanationDrawer
          result={inspectingResult}
          testCaseName={`Test Case #${inspectingResult.test_case_id}`}
          onClose={() => setInspectingResult(null)}
        />
      )}

      {/* Output Side-by-side Diff Viewer */}
      {diffingResult && (
        <OutputDiffViewer
          testCaseName={`Test Case #${diffingResult.result.test_case_id}`}
          candidateOutput={diffingResult.result.output || ""}
          baselineOutput={diffingResult.baselineResultText}
          onClose={() => setDiffingResult(null)}
        />
      )}
    </div>
  );
}
