"use client";

import React, { useState } from "react";
import { TestCase, api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { AddTestDrawer } from "./add-test-drawer";
import { ImportDialog } from "./import-dialog";
import {
  ListChecks,
  Plus,
  Upload,
  Search,
  Edit2,
  Trash2,
  RotateCcw,
  Tag,
  CheckCircle2,
  Filter,
} from "lucide-react";

interface TestTableProps {
  projectId: number;
  testCases: TestCase[];
  isLoading: boolean;
  onRefresh: () => void;
}

export function TestTable({
  projectId,
  testCases,
  isLoading,
  onRefresh,
}: TestTableProps) {
  const { showToast } = useToast();

  const [search, setSearch] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [isAddDrawerOpen, setIsAddDrawerOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [editingTest, setEditingTest] = useState<TestCase | null>(null);

  const filteredTests = testCases.filter((tc) => {
    if (!includeInactive && !tc.is_active) return false;
    if (!search.trim()) return true;
    const query = search.toLowerCase();
    return (
      tc.name.toLowerCase().includes(query) ||
      JSON.stringify(tc.inputs).toLowerCase().includes(query)
    );
  });

  const handleDelete = async (testId: number, name: string) => {
    if (!window.confirm(`Deactivate test case "${name}"?`)) return;

    try {
      await api.deleteTestCase(testId);
      showToast(`Test case "${name}" deactivated (soft deleted)`, "info");
      onRefresh();
    } catch (err: any) {
      showToast(err.message || "Failed to deactivate test case", "error");
    }
  };

  const handleReactivate = async (testId: number, name: string) => {
    try {
      await api.reactivateTestCase(testId);
      showToast(`Test case "${name}" reactivated!`, "success");
      onRefresh();
    } catch (err: any) {
      showToast(err.message || "Failed to reactivate test case", "error");
    }
  };

  if (isLoading) {
    return (
      <div className="h-80 rounded-2xl bg-slate-900/60 border border-slate-800 animate-pulse p-6" />
    );
  }

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      {/* Action Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900/80 border border-slate-800">
        <div className="flex items-center gap-3 flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search test cases or input variables..."
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <label className="flex items-center gap-1.5 text-xs text-slate-400 whitespace-nowrap cursor-pointer">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
              className="rounded bg-slate-950 border-slate-700"
            />
            <span>Show Inactive</span>
          </label>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsImportModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-700 transition"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Import CSV / JSON</span>
          </button>

          <button
            onClick={() => {
              setEditingTest(null);
              setIsAddDrawerOpen(true);
            }}
            className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition"
          >
            <Plus className="w-4 h-4" />
            <span>Add Test Case</span>
          </button>
        </div>
      </div>

      {/* Tests Table */}
      {filteredTests.length === 0 ? (
        <div className="text-center py-16 px-4 rounded-2xl bg-slate-900/40 border border-dashed border-slate-800">
          <ListChecks className="w-10 h-10 text-slate-500 mx-auto mb-2" />
          <h3 className="text-sm font-bold text-white mb-1">No Test Cases Found</h3>
          <p className="text-xs text-slate-400 mb-4">
            {search
              ? "No test cases matched your filter criteria."
              : "Add inputs and assertions to test prompt quality and prevent regressions."}
          </p>
          {!search && (
            <button
              onClick={() => {
                setEditingTest(null);
                setIsAddDrawerOpen(true);
              }}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl transition"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create Test Case</span>
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/90 shadow-xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4">Test Case Name</th>
                <th className="py-3 px-4">Input Parameters</th>
                <th className="py-3 px-4">Configured Checks</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {filteredTests.map((tc) => (
                <tr
                  key={tc.id}
                  className={`hover:bg-slate-800/40 transition ${
                    !tc.is_active ? "opacity-60 bg-slate-950/40" : ""
                  }`}
                >
                  <td className="py-3.5 px-4 font-semibold text-white max-w-[220px] truncate">
                    {tc.name}
                  </td>

                  <td className="py-3.5 px-4 max-w-[260px]">
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(tc.inputs || {}).map(([key, val]) => (
                        <span
                          key={key}
                          className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-300 font-mono truncate max-w-[120px]"
                          title={`${key}: ${JSON.stringify(val)}`}
                        >
                          <span className="text-slate-500">{key}:</span>{" "}
                          {typeof val === "object" ? JSON.stringify(val) : String(val)}
                        </span>
                      ))}
                    </div>
                  </td>

                  <td className="py-3.5 px-4 max-w-[220px]">
                    <div className="flex flex-wrap gap-1">
                      {tc.assertions && tc.assertions.length > 0 ? (
                        tc.assertions.map((a, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded bg-indigo-950/50 text-indigo-300 border border-indigo-800/80 text-[10px] font-medium"
                          >
                            {a.type}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-600 italic">None</span>
                      )}
                    </div>
                  </td>

                  <td className="py-3.5 px-4">
                    {tc.is_active ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/40 border border-emerald-800/60 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Active</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500 bg-slate-950 border border-slate-800 px-2 py-0.5 rounded-full">
                        <span>Inactive</span>
                      </span>
                    )}
                  </td>

                  <td className="py-3.5 px-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {tc.is_active ? (
                        <>
                          <button
                            onClick={() => {
                              setEditingTest(tc);
                              setIsAddDrawerOpen(true);
                            }}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
                            title="Edit Test Case"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDelete(tc.id, tc.name)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 transition"
                            title="Deactivate Test Case"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleReactivate(tc.id, tc.name)}
                          className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/40 rounded-lg transition"
                          title="Reactivate Test Case"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Reactivate</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add / Edit Drawer */}
      {isAddDrawerOpen && (
        <AddTestDrawer
          projectId={projectId}
          existingTest={editingTest}
          onClose={() => {
            setIsAddDrawerOpen(false);
            setEditingTest(null);
          }}
          onSaved={() => {
            onRefresh();
          }}
        />
      )}

      {/* Import Modal */}
      {isImportModalOpen && (
        <ImportDialog
          projectId={projectId}
          onClose={() => setIsImportModalOpen(false)}
          onSuccess={() => {
            onRefresh();
          }}
        />
      )}
    </div>
  );
}
