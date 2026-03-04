/**
 * client.ts — Fetch wrapper typé pour l'API Queen V1.
 * Ajoute automatiquement le token Bearer si présent dans localStorage.
 */

const BASE = "/api";

function getToken(): string | null {
  try {
    return localStorage.getItem("queen_token");
  } catch {
    return null;
  }
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  const token = getToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: headers(),
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
}

// ─── Goals ──────────────────────────────────────────────────

import type {
  Goal, Run, Job, Patch, AuditEntry, LogEntry,
  Stats, HealthResponse, MetricsResponse,
  TimelineResponse, Settings,
} from "./types";

export const goals = {
  list: (status?: string) => get<Goal[]>(status ? `/goals?status=${status}` : "/goals"),
  get: (id: string) => get<Goal>(`/goals/${id}`),
  create: (data: { title: string; description?: string; constraints?: Record<string, unknown> }) =>
    post<{ goal_id: string; status: string }>("/goals", data),
  pause: (id: string) => post<{ status: string }>(`/goals/${id}/pause`),
  resume: (id: string) => post<{ status: string }>(`/goals/${id}/resume`),
};

// ─── Runs ───────────────────────────────────────────────────

export const runs = {
  list: (goalId?: string) => get<Run[]>(goalId ? `/runs?goal_id=${goalId}` : "/runs"),
  get: (id: string) => get<Run>(`/runs/${id}`),
  timeline: (id: string) => get<TimelineResponse>(`/runs/${id}/timeline`),
};

// ─── Jobs ───────────────────────────────────────────────────

export const jobs = {
  list: (params?: { run_id?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.run_id) qs.set("run_id", params.run_id);
    if (params?.status) qs.set("status", params.status);
    const q = qs.toString();
    return get<Job[]>(q ? `/jobs?${q}` : "/jobs");
  },
  get: (id: string) => get<Job>(`/jobs/${id}`),
  retry: (id: string) => post<{ status: string }>(`/jobs/${id}/retry`),
  cancel: (id: string) => post<{ status: string }>(`/jobs/${id}/cancel`),
};

// ─── Patches ────────────────────────────────────────────────

export const patches = {
  list: (goalId?: string) => get<Patch[]>(goalId ? `/patches?goal_id=${goalId}` : "/patches"),
  get: (id: string) => get<Patch>(`/patches/${id}`),
  diff: (id: string) => get<{ patch_id: string; diff: string }>(`/patches/${id}/diff`),
  approve: (id: string, actor = "user") => post<{ status: string }>(`/patches/${id}/approve`, { actor }),
  apply: (id: string, actor = "user") => post<{ status: string }>(`/patches/${id}/apply`, { actor }),
  reject: (id: string, actor = "user", reason = "") =>
    post<{ status: string }>(`/patches/${id}/reject`, { actor, reason }),
  rollback: (id: string, actor = "user") => post<{ status: string }>(`/patches/${id}/rollback`, { actor }),
};

// ─── Monitoring ─────────────────────────────────────────────

export const monitoring = {
  stats: () => get<Stats>("/stats"),
  health: () => get<HealthResponse>("/health"),
  metrics: () => get<MetricsResponse>("/metrics"),
  logs: (count = 100) => get<LogEntry[]>(`/logs?count=${count}`),
  audit: (params?: { entity_type?: string; entity_id?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.entity_type) qs.set("entity_type", params.entity_type);
    if (params?.entity_id) qs.set("entity_id", params.entity_id);
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return get<AuditEntry[]>(q ? `/audit?${q}` : "/audit");
  },
  settings: () => get<Settings>("/settings"),
};
