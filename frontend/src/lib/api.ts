// Frontend API client for PromptCheck FastAPI backend

export const API_BASE_URL =
  typeof window !== "undefined"
    ? window.location.origin
    : process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface Project {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  has_api_key: boolean;
  baseline_run_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface PromptVersion {
  id: number;
  prompt_id: number;
  version_number: number;
  content: string;
  content_hash: string;
  commit_message: string | null;
  created_at: string;
}

export interface PromptItem {
  id: number;
  project_id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  latest_version?: PromptVersion | null;
  versions?: PromptVersion[];
}

export interface TestCase {
  id: number;
  project_id: number;
  name: string;
  inputs: Record<string, any>;
  expected_output: string | null;
  assertions: Array<Record<string, any>>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RunResult {
  id: number;
  run_id: number;
  test_case_id: number;
  status: "pending" | "running" | "passed" | "failed" | "error" | "cancelled";
  rendered_prompt: string | null;
  output: string | null;
  error_message: string | null;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cached: boolean;
  score: number | null;
  classification:
    | "regression"
    | "soft_regression"
    | "improvement"
    | "unchanged"
    | "inconclusive"
    | "passed"
    | "failed"
    | "added"
    | "removed"
    | "error"
    | null;
  comparison_details: {
    score_delta?: number;
    reason?: string;
    details?: Record<string, any>;
    is_flaky?: boolean;
    baseline_status?: string;
    candidate_status?: string;
    baseline_score?: number;
    candidate_score?: number;
  } | null;
  assertion_results: Array<{
    type: string;
    passed: boolean;
    score: number;
    reason: string;
    details: Record<string, any>;
  }>;
  retry_count: number;
  created_at: string;
}

export interface RunSummary {
  baseline_run_id: number | null;
  total_tests: number;
  baseline_tests: number;
  common_tests: number;
  added_tests: number;
  removed_tests: number;
  removed_test_case_ids?: number[];
  passed_tests: number;
  failed_tests: number;
  regressions: number;
  soft_regressions: number;
  improvements: number;
  unchanged: number;
  inconclusive: number;
  flaky_tests: number;
  candidate_avg_score: number;
  baseline_avg_score: number;
  score_delta: number;
  candidate_pass_rate: number;
  baseline_pass_rate: number;
  pass_rate_delta: number;
  verdict:
    | "passed"
    | "regression"
    | "soft_regression"
    | "improvement"
    | "failed"
    | "inconclusive";
  has_regressions: boolean;
  has_soft_regressions: boolean;
  computed_at: string;
}

export interface Run {
  id: number;
  project_id: number;
  prompt_version_id: number;
  baseline_run_id: number | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  error_message: string | null;
  summary: RunSummary | null;
  heartbeat_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  results?: RunResult[];
}

export function formatApiErrorMessage(detail: any): string {
  if (!detail) return "An unexpected error occurred.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((err) => {
        if (typeof err === "string") return err;
        const loc = Array.isArray(err.loc)
          ? err.loc.filter((l: any) => l !== "body").join(" ")
          : "";
        const cleanMsg = err.msg || err.message || "";
        return loc ? `${loc}: ${cleanMsg}` : cleanMsg;
      })
      .filter(Boolean);
    return messages.length > 0 ? messages.join(". ") : "Invalid input provided.";
  }
  if (typeof detail === "object") {
    if (detail.message) return String(detail.message);
    if (detail.detail) return formatApiErrorMessage(detail.detail);
    try {
      return JSON.stringify(detail);
    } catch {
      return "An unexpected error occurred.";
    }
  }
  return String(detail);
}

export class ApiError extends Error {
  status: number;
  detail: any;
  constructor(status: number, detail: any) {
    const msg = formatApiErrorMessage(detail);
    super(msg);
    this.status = status;
    this.detail = detail;
  }
}

// Token storage helper
export const authStorage = {
  getToken: (): string | null => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("promptcheck_token");
  },
  setToken: (token: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("promptcheck_token", token);
    }
  },
  clearToken: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("promptcheck_token");
    }
  },
};

async function fetchWithAuth(
  endpoint: string,
  options: RequestInit = {}
): Promise<any> {
  const token = authStorage.getToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (
    !headers.has("Content-Type") &&
    !(options.body instanceof FormData) &&
    options.method &&
    options.method !== "GET"
  ) {
    headers.set("Content-Type", "application/json");
  }

  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    // If unauthorized, clear token
    if (typeof window !== "undefined" && !endpoint.includes("/auth/")) {
      authStorage.clearToken();
    }
  }

  if (!response.ok) {
    let errorDetail = "An unexpected error occurred.";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson;
    } catch {
      errorDetail = await response.text();
    }
    throw new ApiError(response.status, errorDetail);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  // Auth
  register: (data: { email: string; password: string; full_name?: string }) =>
    fetchWithAuth("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: async (email: string, password: string) => {
    const data = await fetchWithAuth("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    if (data?.access_token) {
      authStorage.setToken(data.access_token);
    }
    return data;
  },

  getCurrentUser: (): Promise<User> => fetchWithAuth("/api/auth/me"),

  // Projects
  listProjects: (): Promise<Project[]> => fetchWithAuth("/api/projects"),

  createProject: (data: {
    name: string;
    description?: string;
    gemini_api_key?: string;
  }): Promise<Project> =>
    fetchWithAuth("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getProject: (projectId: number): Promise<Project> =>
    fetchWithAuth(`/api/projects/${projectId}`),

  updateProject: (
    projectId: number,
    data: { name?: string; description?: string; gemini_api_key?: string }
  ): Promise<Project> =>
    fetchWithAuth(`/api/projects/${projectId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProject: (projectId: number) =>
    fetchWithAuth(`/api/projects/${projectId}`, { method: "DELETE" }),

  // Prompts & Versions
  listPrompts: (projectId: number): Promise<PromptItem[]> =>
    fetchWithAuth(`/api/projects/${projectId}/prompts`),

  createPrompt: (
    projectId: number,
    data: {
      name: string;
      description?: string;
      initial_version_content: string;
      commit_message?: string;
    }
  ): Promise<PromptItem> =>
    fetchWithAuth(`/api/projects/${projectId}/prompts`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listPromptVersions: (promptId: number): Promise<PromptVersion[]> =>
    fetchWithAuth(`/api/prompts/${promptId}/versions`),

  createPromptVersion: (
    promptId: number,
    data: { content: string; commit_message?: string }
  ): Promise<PromptVersion> =>
    fetchWithAuth(`/api/prompts/${promptId}/versions`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Test Cases
  listTestCases: (
    projectId: number,
    includeInactive = false
  ): Promise<TestCase[]> =>
    fetchWithAuth(
      `/api/projects/${projectId}/test-cases?include_inactive=${includeInactive}`
    ),

  createTestCase: (
    projectId: number,
    data: {
      name: string;
      inputs?: Record<string, any>;
      expected_output?: string;
      assertions?: Array<Record<string, any>>;
    }
  ): Promise<TestCase> =>
    fetchWithAuth(`/api/projects/${projectId}/test-cases`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateTestCase: (
    testCaseId: number,
    data: {
      name?: string;
      inputs?: Record<string, any>;
      expected_output?: string;
      assertions?: Array<Record<string, any>>;
      is_active?: boolean;
    }
  ): Promise<TestCase> =>
    fetchWithAuth(`/api/test-cases/${testCaseId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteTestCase: (testCaseId: number): Promise<TestCase> =>
    fetchWithAuth(`/api/test-cases/${testCaseId}`, { method: "DELETE" }),

  reactivateTestCase: (testCaseId: number): Promise<TestCase> =>
    fetchWithAuth(`/api/test-cases/${testCaseId}/reactivate`, {
      method: "POST",
    }),

  batchImportTestCases: (
    projectId: number,
    testCases: Array<{
      name: string;
      inputs?: Record<string, any>;
      expected_output?: string;
      assertions?: Array<Record<string, any>>;
    }>
  ): Promise<TestCase[]> =>
    fetchWithAuth(`/api/projects/${projectId}/test-cases/batch`, {
      method: "POST",
      body: JSON.stringify(testCases),
    }),

  importCsvTestCases: (
    projectId: number,
    file: File
  ): Promise<{ message: string; imported_count: number }> => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchWithAuth(`/api/projects/${projectId}/test-cases/import/csv`, {
      method: "POST",
      body: formData,
    });
  },

  // Runs & Regressions
  createRun: (
    projectId: number,
    data: {
      prompt_version_id: number;
      enable_cache?: boolean;
      baseline_run_id?: number | null;
    }
  ): Promise<Run> =>
    fetchWithAuth(`/api/projects/${projectId}/runs`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listRuns: (projectId: number): Promise<Run[]> =>
    fetchWithAuth(`/api/projects/${projectId}/runs`),

  getRun: (runId: number): Promise<Run> => fetchWithAuth(`/api/runs/${runId}`),

  getRunResults: (runId: number): Promise<RunResult[]> =>
    fetchWithAuth(`/api/runs/${runId}/results`),

  cancelRun: (runId: number): Promise<Run> =>
    fetchWithAuth(`/api/runs/${runId}/cancel`, { method: "POST" }),

  setRunBaseline: (
    runId: number,
    data?: { baseline_run_id?: number | null; set_as_project_baseline?: boolean }
  ): Promise<Run> =>
    fetchWithAuth(`/api/runs/${runId}/baseline`, {
      method: "POST",
      body: JSON.stringify(data || { set_as_project_baseline: true }),
    }),
};
