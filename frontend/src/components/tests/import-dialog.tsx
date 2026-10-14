"use client";

import React, { useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/providers";
import { Upload, FileText, Download, X, CheckCircle2, AlertCircle } from "lucide-react";

interface ImportDialogProps {
  projectId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export function ImportDialog({ projectId, onClose, onSuccess }: ImportDialogProps) {
  const { showToast } = useToast();

  const [file, setFile] = useState<File | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [mode, setMode] = useState<"csv" | "json">("csv");
  const [previewRows, setPreviewRows] = useState<any[]>([]);
  const [isImporting, setIsImporting] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setParseError(null);

    if (f.name.endsWith(".csv")) {
      const text = await f.text();
      const lines = text.split("\n").filter((l) => l.trim().length > 0);
      if (lines.length > 1) {
        const headers = lines[0].split(",").map((h) => h.trim());
        const preview = lines.slice(1, 6).map((line) => {
          const cells = line.split(",").map((c) => c.trim());
          const obj: Record<string, string> = {};
          headers.forEach((h, i) => {
            obj[h] = cells[i] || "";
          });
          return obj;
        });
        setPreviewRows(preview);
      }
    }
  };

  const handleJsonChange = (text: string) => {
    setJsonText(text);
    setParseError(null);
    try {
      if (text.trim()) {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed)) {
          setPreviewRows(parsed.slice(0, 5));
        } else {
          setPreviewRows([parsed]);
        }
      } else {
        setPreviewRows([]);
      }
    } catch (err: any) {
      setParseError("Invalid JSON syntax: " + err.message);
      setPreviewRows([]);
    }
  };

  const handleDownloadSampleCsv = () => {
    const csvContent =
      "name,inputs,expected_output,assertions\n" +
      "Late Delivery,\"{\"\"customer_name\"\": \"Alice\", \"\"order_id\"\": \"ORD-12345\"}\",\"Hello Alice...\",\"[{\"\"type\"\": \"contains\", \"\"substring\"\": \"Alice\"}]\"\n" +
      "Refund Request,\"{\"\"customer_name\"\": \"Bob\", \"\"order_id\"\": \"ORD-67890\"}\",\"Hello Bob...\",\"[{\"\"type\"\": \"contains\", \"\"substring\"\": \"Bob\"}]\"\n";

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "promptcheck_sample_tests.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDownloadSampleJson = () => {
    const jsonContent = JSON.stringify(
      [
        {
          name: "Late Delivery Inquiry",
          inputs: { customer_name: "Alice", order_id: "ORD-12345" },
          expected_output: "Hello Alice, your order is being tracked.",
          assertions: [{ type: "contains", substring: "Alice" }],
        },
        {
          name: "Refund Status",
          inputs: { customer_name: "Bob", order_id: "ORD-67890" },
          expected_output: "Hello Bob, your refund is processed.",
          assertions: [{ type: "contains", substring: "Bob" }],
        },
      ],
      null,
      2
    );

    const blob = new Blob([jsonContent], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "promptcheck_sample_tests.json");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleExecuteImport = async () => {
    setIsImporting(true);
    try {
      if (mode === "csv") {
        if (!file) throw new Error("Please select a CSV file to upload");
        const res = await api.importCsvTestCases(projectId, file);
        showToast(res.message || "CSV test cases imported successfully!", "success");
      } else {
        if (!jsonText.trim()) throw new Error("Please enter JSON test cases");
        const parsed = JSON.parse(jsonText);
        const list = Array.isArray(parsed) ? parsed : [parsed];
        await api.batchImportTestCases(projectId, list);
        showToast(`Imported ${list.length} test cases from JSON!`, "success");
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      showToast(err.message || "Import failed", "error");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl animate-in zoom-in-95 duration-150 flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-950/60 text-indigo-400 border border-indigo-800/80">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Import Test Cases</h3>
              <p className="text-xs text-slate-400">
                Bulk upload test cases from CSV or JSON format.
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

        {/* Format Selector & Sample Download */}
        <div className="flex items-center justify-between gap-4 mb-4">
          <div className="flex border border-slate-800 rounded-xl p-0.5 bg-slate-950 text-xs">
            <button
              onClick={() => {
                setMode("csv");
                setPreviewRows([]);
              }}
              className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                mode === "csv"
                  ? "bg-indigo-600 text-white shadow"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              CSV File Upload
            </button>
            <button
              onClick={() => {
                setMode("json");
                setPreviewRows([]);
              }}
              className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                mode === "json"
                  ? "bg-indigo-600 text-white shadow"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Raw JSON Batch
            </button>
          </div>

          <button
            onClick={mode === "csv" ? handleDownloadSampleCsv : handleDownloadSampleJson}
            className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Sample {mode.toUpperCase()}</span>
          </button>
        </div>

        {/* Input Body */}
        <div className="flex-1 overflow-y-auto space-y-4">
          {mode === "csv" ? (
            <div className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-2xl p-8 text-center bg-slate-950/50">
              <input
                type="file"
                accept=".csv"
                id="csv-file-input"
                onChange={handleFileChange}
                className="hidden"
              />
              <label
                htmlFor="csv-file-input"
                className="cursor-pointer flex flex-col items-center"
              >
                <FileText className="w-10 h-10 text-indigo-400 mb-2" />
                <span className="text-sm font-semibold text-white">
                  {file ? file.name : "Click or drag CSV file to upload"}
                </span>
                <span className="text-xs text-slate-500 mt-1">
                  Expected columns: name, inputs, expected_output, assertions
                </span>
              </label>
            </div>
          ) : (
            <div>
              <textarea
                rows={8}
                value={jsonText}
                onChange={(e) => handleJsonChange(e.target.value)}
                placeholder="[&#10;  {&#10;    &quot;name&quot;: &quot;Sample Test&quot;,&#10;    &quot;inputs&quot;: { &quot;query&quot;: &quot;hello&quot; },&#10;    &quot;assertions&quot;: [{ &quot;type&quot;: &quot;contains&quot;, &quot;substring&quot;: &quot;hello&quot; }]&#10;  }&#10;]"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 font-mono text-xs text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              {parseError && (
                <p className="text-xs text-rose-400 mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  <span>{parseError}</span>
                </p>
              )}
            </div>
          )}

          {/* Preview Table */}
          {previewRows.length > 0 && (
            <div className="pt-2">
              <h4 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>Preview (First {previewRows.length} Rows)</span>
              </h4>
              <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-semibold">
                    <tr>
                      <th className="p-2.5">Name</th>
                      <th className="p-2.5">Inputs</th>
                      <th className="p-2.5">Assertions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-slate-300 font-mono text-[11px]">
                    {previewRows.map((r, i) => (
                      <tr key={i} className="hover:bg-slate-900/40">
                        <td className="p-2.5 font-sans font-medium text-white max-w-[150px] truncate">
                          {r.name || `Test #${i + 1}`}
                        </td>
                        <td className="p-2.5 max-w-[200px] truncate text-slate-400">
                          {typeof r.inputs === "object"
                            ? JSON.stringify(r.inputs)
                            : String(r.inputs || "{}")}
                        </td>
                        <td className="p-2.5 max-w-[200px] truncate text-slate-400">
                          {typeof r.assertions === "object"
                            ? JSON.stringify(r.assertions)
                            : String(r.assertions || "[]")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800 mt-4">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition"
          >
            Cancel
          </button>
          <button
            onClick={handleExecuteImport}
            disabled={isImporting || (mode === "csv" && !file) || (mode === "json" && !jsonText.trim())}
            className="flex items-center gap-2 px-5 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-xl shadow-lg transition disabled:opacity-40"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>{isImporting ? "Importing..." : "Import Test Cases"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
