"use client";

import React, { useState } from "react";
import { Plus, Trash2, CheckCircle2, Sliders, Code2, ShieldAlert } from "lucide-react";

export interface AssertionConfig {
  type: "exact" | "contains" | "regex" | "json_schema" | "length" | "semantic" | "llm_judge";
  // exact
  expected?: string;
  case_sensitive?: boolean;
  strip?: boolean;
  // contains
  substring?: string;
  substrings?: string[];
  mode?: "all" | "any";
  negate?: boolean;
  // regex
  pattern?: string;
  // json_schema
  schema?: Record<string, any>;
  // length
  min_length?: number;
  max_length?: number;
  exact_length?: number;
  unit?: "characters" | "words";
  // semantic
  reference_text?: string;
  threshold?: number;
  // llm_judge
  rubric?: string;
  model?: string;
}

interface CheckBuilderProps {
  assertions: AssertionConfig[];
  onChange: (assertions: AssertionConfig[]) => void;
}

export function CheckBuilder({ assertions, onChange }: CheckBuilderProps) {
  const [selectedType, setSelectedType] = useState<AssertionConfig["type"]>("contains");

  const handleAddAssertion = () => {
    let newAssertion: AssertionConfig = { type: selectedType };

    switch (selectedType) {
      case "exact":
        newAssertion = {
          type: "exact",
          expected: "",
          case_sensitive: true,
          strip: false,
        };
        break;
      case "contains":
        newAssertion = {
          type: "contains",
          substring: "",
          mode: "all",
          negate: false,
          case_sensitive: true,
        };
        break;
      case "regex":
        newAssertion = {
          type: "regex",
          pattern: "",
          case_sensitive: true,
        };
        break;
      case "json_schema":
        newAssertion = {
          type: "json_schema",
          schema: {
            type: "object",
            properties: { status: { type: "string" } },
            required: ["status"],
          },
        };
        break;
      case "length":
        newAssertion = {
          type: "length",
          min_length: 10,
          max_length: 500,
          unit: "characters",
        };
        break;
      case "semantic":
        newAssertion = {
          type: "semantic",
          reference_text: "",
          threshold: 0.8,
        };
        break;
      case "llm_judge":
        newAssertion = {
          type: "llm_judge",
          rubric: "Ensure the candidate output is polite, accurate, and directly answers the user prompt.",
          model: "gemini-2.5-flash",
        };
        break;
    }

    onChange([...assertions, newAssertion]);
  };

  const handleUpdate = (index: number, updated: AssertionConfig) => {
    const list = [...assertions];
    list[index] = updated;
    onChange(list);
  };

  const handleRemove = (index: number) => {
    onChange(assertions.filter((_, idx) => idx !== index));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <label className="text-xs font-bold text-slate-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-indigo-400" />
          <span>Evaluation Checks / Assertions ({assertions.length})</span>
        </label>

        {/* Add check dropdown */}
        <div className="flex items-center gap-2">
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value as AssertionConfig["type"])}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-indigo-500 font-medium"
          >
            <option value="exact">1. Exact Match</option>
            <option value="contains">2. Contains Substring</option>
            <option value="regex">3. Regular Expression</option>
            <option value="json_schema">4. JSON Schema</option>
            <option value="length">5. Length Bounds</option>
            <option value="semantic">6. Semantic Similarity (Gemini)</option>
            <option value="llm_judge">7. LLM-as-Judge</option>
          </select>

          <button
            type="button"
            onClick={handleAddAssertion}
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg transition"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Check</span>
          </button>
        </div>
      </div>

      {assertions.length === 0 ? (
        <p className="text-xs text-slate-500 italic py-2">
          No checks configured yet. Add at least one check to validate model outputs.
        </p>
      ) : (
        <div className="space-y-3">
          {assertions.map((assertion, index) => (
            <div
              key={index}
              className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 bg-indigo-950/60 border border-indigo-800 px-2 py-0.5 rounded">
                  {assertion.type}
                </span>
                <button
                  type="button"
                  onClick={() => handleRemove(index)}
                  className="p-1 text-slate-500 hover:text-rose-400 transition"
                  title="Remove Check"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Exact Evaluator */}
              {assertion.type === "exact" && (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={assertion.expected || ""}
                    onChange={(e) =>
                      handleUpdate(index, { ...assertion, expected: e.target.value })
                    }
                    placeholder="Exact expected string..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                  <div className="flex items-center gap-4 text-xs text-slate-400">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={assertion.case_sensitive ?? true}
                        onChange={(e) =>
                          handleUpdate(index, {
                            ...assertion,
                            case_sensitive: e.target.checked,
                          })
                        }
                        className="rounded bg-slate-900 border-slate-700"
                      />
                      <span>Case sensitive</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={assertion.strip ?? false}
                        onChange={(e) =>
                          handleUpdate(index, { ...assertion, strip: e.target.checked })
                        }
                        className="rounded bg-slate-900 border-slate-700"
                      />
                      <span>Strip whitespace</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Contains Evaluator */}
              {assertion.type === "contains" && (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={
                      assertion.substring ||
                      (assertion.substrings ? assertion.substrings.join(", ") : "")
                    }
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val.includes(",")) {
                        handleUpdate(index, {
                          ...assertion,
                          substrings: val.split(",").map((s) => s.trim()).filter(Boolean),
                          substring: undefined,
                        });
                      } else {
                        handleUpdate(index, {
                          ...assertion,
                          substring: val,
                          substrings: undefined,
                        });
                      }
                    }}
                    placeholder="Required substring(s) (comma-separated for multiple)..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                  <div className="flex items-center gap-4 text-xs text-slate-400">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={assertion.negate ?? false}
                        onChange={(e) =>
                          handleUpdate(index, { ...assertion, negate: e.target.checked })
                        }
                        className="rounded bg-slate-900 border-slate-700"
                      />
                      <span className={assertion.negate ? "text-rose-400 font-semibold" : ""}>
                        Negate (Must NOT contain)
                      </span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={assertion.case_sensitive ?? true}
                        onChange={(e) =>
                          handleUpdate(index, {
                            ...assertion,
                            case_sensitive: e.target.checked,
                          })
                        }
                        className="rounded bg-slate-900 border-slate-700"
                      />
                      <span>Case sensitive</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Regex Evaluator */}
              {assertion.type === "regex" && (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={assertion.pattern || ""}
                    onChange={(e) =>
                      handleUpdate(index, { ...assertion, pattern: e.target.value })
                    }
                    placeholder="Regex pattern (e.g. ^ORD-\d{5}$)..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              )}

              {/* JSON Schema Evaluator */}
              {assertion.type === "json_schema" && (
                <div className="space-y-2">
                  <textarea
                    rows={3}
                    value={
                      assertion.schema
                        ? JSON.stringify(assertion.schema, null, 2)
                        : ""
                    }
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        handleUpdate(index, { ...assertion, schema: parsed });
                      } catch {
                        // Keep text update
                      }
                    }}
                    placeholder="JSON Schema object..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-mono placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
              )}

              {/* Length Evaluator */}
              {assertion.type === "length" && (
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <label className="text-slate-400 block mb-1">Min Length</label>
                    <input
                      type="number"
                      value={assertion.min_length ?? ""}
                      onChange={(e) =>
                        handleUpdate(index, {
                          ...assertion,
                          min_length: e.target.value ? Number(e.target.value) : undefined,
                        })
                      }
                      placeholder="e.g. 10"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-white focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 block mb-1">Max Length</label>
                    <input
                      type="number"
                      value={assertion.max_length ?? ""}
                      onChange={(e) =>
                        handleUpdate(index, {
                          ...assertion,
                          max_length: e.target.value ? Number(e.target.value) : undefined,
                        })
                      }
                      placeholder="e.g. 500"
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-white focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 block mb-1">Unit</label>
                    <select
                      value={assertion.unit || "characters"}
                      onChange={(e) =>
                        handleUpdate(index, {
                          ...assertion,
                          unit: e.target.value as "characters" | "words",
                        })
                      }
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-white focus:outline-none"
                    >
                      <option value="characters">Characters</option>
                      <option value="words">Words</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Semantic Similarity Evaluator */}
              {assertion.type === "semantic" && (
                <div className="space-y-2">
                  <textarea
                    rows={2}
                    value={assertion.reference_text || ""}
                    onChange={(e) =>
                      handleUpdate(index, {
                        ...assertion,
                        reference_text: e.target.value,
                      })
                    }
                    placeholder="Reference text for Gemini cosine similarity..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                  <div className="flex items-center gap-3 text-xs text-slate-400">
                    <span>Similarity Threshold:</span>
                    <input
                      type="range"
                      min="0.5"
                      max="1.0"
                      step="0.05"
                      value={assertion.threshold ?? 0.8}
                      onChange={(e) =>
                        handleUpdate(index, {
                          ...assertion,
                          threshold: Number(e.target.value),
                        })
                      }
                      className="w-32 accent-indigo-500"
                    />
                    <span className="font-mono text-white font-semibold">
                      {(assertion.threshold ?? 0.8).toFixed(2)}
                    </span>
                  </div>
                </div>
              )}

              {/* LLM Judge Evaluator */}
              {assertion.type === "llm_judge" && (
                <div className="space-y-2">
                  <textarea
                    rows={2}
                    value={assertion.rubric || ""}
                    onChange={(e) =>
                      handleUpdate(index, { ...assertion, rubric: e.target.value })
                    }
                    placeholder="Evaluation rubric criteria for the judge model..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                  <div className="flex items-center gap-3 text-xs">
                    <label className="text-slate-400">Judge Model:</label>
                    <select
                      value={assertion.model || "gemini-2.5-flash"}
                      onChange={(e) =>
                        handleUpdate(index, { ...assertion, model: e.target.value })
                      }
                      className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-white focus:outline-none"
                    >
                      <option value="gemini-2.5-flash">gemini-2.5-flash (Fast & Cost-effective)</option>
                      <option value="gemini-2.5-pro">gemini-2.5-pro (Deep reasoning)</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
