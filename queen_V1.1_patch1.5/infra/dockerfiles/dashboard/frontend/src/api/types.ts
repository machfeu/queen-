// ─── Enums ──────────────────────────────────────────────────

export type GoalStatus =
  | "pending"
  | "planning"
  | "running"
  | "paused"
  | "completed"
  | "failed";

export type JobType = "research" | "codegen" | "test" | "eval" | "patch";

export type JobStatus =
  | "queued"
  | "running"
  | "success"
  | "failed"
  | "timeout"
  | "cancelled";

export type RunStatus =
  | "running"
  | "gates_pending"
  | "gates_passed"
  | "gates_failed"
  | "approved"
  | "applied"
  | "rejected"
  | "rolled_back";

export type PatchStatus =
  | "generated"
  | "gates_running"
  | "gates_passed"
  | "gates_failed"
  | "approved"
  | "applied"
  | "rejected"
  | "rolled_back";

// ─── Models ─────────────────────────────────────────────────

export interface Goal {
  id: string;
  title: string;
  description: string;
  constraints: Record<string, unknown>;
  status: GoalStatus;
  created_at: string;
  updated_at: string;
}

export interface Run {
  id: string;
  goal_id: string;
  status: RunStatus;
  plan: PlanJob[];
  score: number;
  score_justification: string;
  patch_id: string;
  created_at: string;
  finished_at: string;
}

export interface PlanJob {
  step: number;
  job_type: JobType;
  title: string;
  description: string;
  depends_on: number[];
  estimated_duration_seconds: number;
}

export interface Job {
  id: string;
  run_id: string;
  goal_id: string;
  job_type: JobType;
  payload: Record<string, unknown>;
  status: JobStatus;
  result: Record<string, unknown>;
  logs: string;
  worker_id: string;
  timeout_seconds: number;
  max_output_bytes: number;
  created_at: string;
  started_at: string;
  finished_at: string;
}

export interface Patch {
  id: string;
  run_id: string;
  goal_id: string;
  diff_content: string;
  status: PatchStatus;
  gate_results: Record<string, GateResult>;
  applied_at: string;
  approved_by: string;
  created_at: string;
}

export interface GateResult {
  passed: boolean;
  violations?: string[];
  errors?: string[];
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  action: string;
  entity_type: string;
  entity_id: string;
  actor: string;
  details: Record<string, unknown>;
}

// ─── API Responses ──────────────────────────────────────────

export interface Stats {
  goals_total: number;
  goals_running: number;
  runs_total: number;
  jobs_total: number;
  jobs_running: number;
  patches_total: number;
  patches_applied: number;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  components: {
    database: { status: string };
    redis: { status: string; queue_length?: number };
    llm: { status: string; provider?: string };
  };
}

export interface MetricsResponse {
  disk?: { total_gb: number; used_gb: number; free_gb: number; percent_used: number };
  memory?: { total_mb: number; available_mb: number; used_mb: number; percent_used: number };
  cpu?: { load_1m: number; load_5m: number; load_15m: number };
  gpu?: {
    name: string;
    memory_used_mb: number;
    memory_total_mb: number;
    utilization_percent: number;
    temperature_c: number;
  };
}

export interface TimelineResponse {
  run_id: string;
  goal_id: string;
  run_status: RunStatus;
  score: number;
  patch_id: string;
  timeline: TimelineItem[];
}

export interface TimelineItem {
  job_id: string;
  step: number;
  job_type: JobType;
  title: string;
  status: JobStatus;
  created_at: string;
  started_at: string;
  finished_at: string;
  worker_id: string;
}

export interface LogEntry {
  level: string;
  source: string;
  message: string;
  timestamp: number;
}

export interface Settings {
  llm_provider: string;
  ollama_model: string;
  ollama_url: string;
  openai_model: string;
  policy_job_timeout: number;
  policy_max_job_timeout: number;
  policy_max_output_bytes: number;
  policy_max_jobs_per_run: number;
  policy_max_concurrent_jobs: number;
  require_manual_approval: boolean;
}

// ─── Patch 1.2: Roles & Skills ─────────────────────────────

export interface RoleDef {
  name: string;
  description: string;
  icon?: string;
  user_prompt?: string;
  tools?: string[];
  skills?: string[];
  default_constraints?: Record<string, unknown>;
  enabled?: boolean;
}

export interface SkillDef {
  name: string;
  summary?: string;
  content?: string;
}

