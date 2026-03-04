/**
 * hooks.ts — React Query hooks pour toute l'app.
 * Chaque hook encapsule un appel client.ts + cache + refetch auto.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { goals, runs, jobs, patches, monitoring } from "./client";

const REFETCH = 5_000; // 5s auto-refresh pour les données live

// ─── Goals ──────────────────────────────────────────────────

export function useGoals(status?: string) {
  return useQuery({
    queryKey: ["goals", status],
    queryFn: () => goals.list(status),
    refetchInterval: REFETCH,
  });
}

export function useGoal(id: string) {
  return useQuery({
    queryKey: ["goal", id],
    queryFn: () => goals.get(id),
    enabled: !!id,
  });
}

export function useCreateGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: goals.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals"] }),
  });
}

export function usePauseGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => goals.pause(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals"] }),
  });
}

export function useResumeGoal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => goals.resume(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["goals"] }),
  });
}

// ─── Runs ───────────────────────────────────────────────────

export function useRuns(goalId?: string) {
  return useQuery({
    queryKey: ["runs", goalId],
    queryFn: () => runs.list(goalId),
    refetchInterval: REFETCH,
  });
}

export function useRun(id: string) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => runs.get(id),
    enabled: !!id,
    refetchInterval: REFETCH,
  });
}

export function useRunTimeline(id: string) {
  return useQuery({
    queryKey: ["run-timeline", id],
    queryFn: () => runs.timeline(id),
    enabled: !!id,
    refetchInterval: REFETCH,
  });
}

// ─── Jobs ───────────────────────────────────────────────────

export function useJobs(params?: { run_id?: string; status?: string }) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => jobs.list(params),
    refetchInterval: REFETCH,
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => jobs.get(id),
    enabled: !!id,
  });
}

export function useRetryJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => jobs.retry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useCancelJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => jobs.cancel(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

// ─── Patches ────────────────────────────────────────────────

export function usePatches(goalId?: string) {
  return useQuery({
    queryKey: ["patches", goalId],
    queryFn: () => patches.list(goalId),
    refetchInterval: REFETCH,
  });
}

export function usePatch(id: string) {
  return useQuery({
    queryKey: ["patch", id],
    queryFn: () => patches.get(id),
    enabled: !!id,
  });
}

export function usePatchDiff(id: string) {
  return useQuery({
    queryKey: ["patch-diff", id],
    queryFn: () => patches.diff(id),
    enabled: !!id,
  });
}

export function useApprovePatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => patches.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["patches"] }),
  });
}

export function useApplyPatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => patches.apply(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["patches"] }),
  });
}

export function useRejectPatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      patches.reject(id, "user", reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["patches"] }),
  });
}

export function useRollbackPatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => patches.rollback(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["patches"] }),
  });
}

// ─── Monitoring ─────────────────────────────────────────────

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: monitoring.stats,
    refetchInterval: REFETCH,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: monitoring.health,
    refetchInterval: 10_000,
  });
}

export function useMetrics() {
  return useQuery({
    queryKey: ["metrics"],
    queryFn: monitoring.metrics,
    refetchInterval: REFETCH,
  });
}

export function useLogs(count = 100) {
  return useQuery({
    queryKey: ["logs", count],
    queryFn: () => monitoring.logs(count),
    refetchInterval: 3_000,
  });
}

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: monitoring.settings,
    staleTime: 60_000,
  });
}
