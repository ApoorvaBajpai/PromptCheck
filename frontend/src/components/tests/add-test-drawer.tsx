"use client";

import React, { useState } from "react";
import { TestCase, api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { CheckBuilder, AssertionConfig } from "./check-builder";
import { X, Save, Plus, Trash2, SlidersHorizontal } from "lucide-react";

interface AddTestDrawerProps {
  projectId: number;
  existingTest?: TestCase | null;
  onClose: () => void;
  onSaved: () => void;
}

export function AddTestDrawer({
  projectId,
  existingTest,
  onClose,
  onSaved,
}: AddTestDrawerProps) {
  const { showToast } = useToast();

  const [name, setName] = useState(existingTest?.name || "");
  const [expectedOutput, setExpectedOutput] = useState(
    existingTest?.expected_output || ""
  );

  // Key-Value input builder pairs
  const initialInputs = existingTest?.inputs
    ? Object.entries(existingTest.inputs).map(([k, v]) => ({
        key: k,
        val: typeof v === "object" ? JSON.stringify(v) : String(v),
      }))
    : [{ key: "query", val: "" }];

  const [inputPairs, setInputPairs] = useState(initialInputs);
  const [assertions, setAssertions] = useState<AssertionConfig[]>(
    (existingTest?.assertions as AssertionConfig[]) || [
      { type: "contains", substring: "" },
    ]
  );
  const [isSaving, setIsSaving] = useState(false);

  const handleAddInputPair = () => {
    setInputPairs([...inputPairs, { key: "", val: "" }]);
  };

  const handleRemoveInputPair = (idx: number) => {
    setInputPairs(inputPairs.filter((_, i) => i !== idx));
  };

  const handleUpdateInputPair = (
    idx: number,
    field: "key" | "val",
    value: string
  ) => {
    const next = [...inputPairs];
    next[idx][field] = value;
    setInputPairs(next);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    // Convert key-value pairs to dict
    const inputsDict: Record<string, any> = {};
    for (const pair of inputPairs) {
      if (pair.key.trim()) {
        try {
          inputsDict[pair.key.trim()] = JSON.parse(pair.val);
        } catch {
          inputsDict[pair.key.trim()] = pair.val;
        }
      }
    }

    setIsSaving(true);
    try {
      if (existingTest) {
        await api.updateTestCase(existingTest.id, {
          name: name.trim(),
          inputs: inputsDict,
          expected_output: expectedOutput.trim() || undefined,
          assertions: assertions,
        });
        showToast(`Test case "${name}" updated`, "success");
      } else {
        await api.createTestCase(projectId, {
          name: name.trim(),
          inputs: inputsDict,
          expected_output: expectedOutput.trim() || undefined,
          assertions: assertions,
        });
        showToast(`Test case "${name}" created`, "success");
      }
      onSaved();
      onClose();
    } catch (err: any) {
      showToast(err.message || "Failed to save test case", "error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/50">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <SlidersHorizontal className="w-4 h-4 text-indigo-400" />
                <span>{existingTest ? "Edit Test Case" : "Add Test Case"}</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Define inputs and evaluation assertions for prompt execution.
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Form Content */}
          <form
            onSubmit={handleSubmit}
            className="flex-1 overflow-y-auto p-6 space-y-6"
          >
            {/* Test Case Name */}
            <div>
              <label className="block text-xs font-bold text-slate-300 mb-1">
                Test Case Name *
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Broken item refund inquiry"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
              />
            </div>

            {/* Input Variables Builder */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold text-slate-300">
                  Input Variables (for Jinja template)
                </label>
                <button
                  type="button"
                  onClick={handleAddInputPair}
                  className="flex items-center gap-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Variable</span>
                </button>
              </div>

              <div className="space-y-2">
                {inputPairs.map((pair, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={pair.key}
                      onChange={(e) =>
                        handleUpdateInputPair(idx, "key", e.target.value)
                      }
                      placeholder="Variable name (e.g. query)"
                      className="w-1/3 bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    <input
                      type="text"
                      value={pair.val}
                      onChange={(e) =>
                        handleUpdateInputPair(idx, "val", e.target.value)
                      }
                      placeholder="Value"
                      className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                    {inputPairs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveInputPair(idx)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Expected Output */}
            <div>
              <label className="block text-xs font-bold text-slate-300 mb-1">
                Expected Output Reference (optional)
              </label>
              <textarea
                rows={2}
                value={expectedOutput}
                onChange={(e) => setExpectedOutput(e.target.value)}
                placeholder="Ideal response reference string..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>

            {/* Check Builder */}
            <CheckBuilder assertions={assertions} onChange={setAssertions} />
          </form>

          {/* Footer Actions */}
          <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={isSaving || !name.trim()}
              className="flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{isSaving ? "Saving..." : "Save Test Case"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
