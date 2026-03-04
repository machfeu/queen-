/**
 * Overview.tsx — Page d'accueil du dashboard.
 * Affiche: stats globales, santé système, runs récents, jobs récents.
 */

import {
  Title, Text, Paper, Group, Badge, Table, Stack, Loader, Alert,
} from "@mantine/core";
import {
  IconTarget, IconRefresh, IconBolt, IconGitPullRequest,
  IconCpu, IconDeviceDesktop, IconAlertCircle,
} from "@tabler/icons-react";
import { useStats, useHealth, useRuns, useJobs, useMetrics } from "../api/hooks";
import { useEvents } from "../ws/useEvents";
import StatCards from "../components/StatCards";
import type { Run, Job } from "../api/types";

function statusColor(s: string): string {
  if (["completed", "success", "applied", "gates_passed", "approved"].includes(s)) return "green";
  if (["failed", "timeout", "rejected", "gates_failed"].includes(s)) return "red";
  if (["running", "gates_running", "gates_pending"].includes(s)) return "blue";
  if (["paused", "planning", "queued"].includes(s)) return "violet";
  return "gray";
}

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}min`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}j`;
}

export default function Overview() {
  const { data: stats, isLoading: loadStats } = useStats();
  const { data: health } = useHealth();
  const { data: runsData } = useRuns();
  const { data: jobsData } = useJobs();
  const { data: metrics } = useMetrics();
  const { events, connected } = useEvents();

  if (loadStats) {
    return <Loader m="xl" />;
  }

  const recentRuns = (runsData ?? []).slice(0, 5);
  const recentJobs = (jobsData ?? []).slice(0, 8);

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Overview</Title>
        <Badge variant="dot" color={connected ? "green" : "gray"} size="sm">
          {connected ? "live" : "polling"}
        </Badge>
      </Group>

      {/* ── Stats ───────────────────────────────── */}
      <StatCards
        items={[
          { label: "Goals", value: stats?.goals_total ?? 0, icon: <IconTarget size={14} />, color: "violet" },
          { label: "Goals actifs", value: stats?.goals_running ?? 0, icon: <IconTarget size={14} />, color: "blue" },
          { label: "Runs", value: stats?.runs_total ?? 0, icon: <IconRefresh size={14} />, color: "teal" },
          { label: "Jobs en cours", value: stats?.jobs_running ?? 0, icon: <IconBolt size={14} />, color: "orange" },
          { label: "Jobs total", value: stats?.jobs_total ?? 0, icon: <IconBolt size={14} />, color: "gray" },
          { label: "Patches", value: stats?.patches_total ?? 0, icon: <IconGitPullRequest size={14} />, color: "cyan" },
          { label: "Patches appliqués", value: stats?.patches_applied ?? 0, icon: <IconGitPullRequest size={14} />, color: "green" },
        ]}
      />

      {/* ── System Health ────────────────────────── */}
      <Paper p="md" radius="md" withBorder>
        <Text fw={600} mb="xs">Santé système</Text>
        <Group gap="lg">
          <HealthBadge label="DB" ok={health?.components?.database?.status === "ok"} />
          <HealthBadge label="Redis" ok={health?.components?.redis?.status === "ok"} />
          <HealthBadge label="LLM" ok={health?.components?.llm?.status === "ok"} />
          {metrics?.cpu && (
            <Text size="sm" c="dimmed">
              <IconCpu size={14} style={{ verticalAlign: "middle" }} />{" "}
              Load: {metrics.cpu.load_1m.toFixed(1)}
            </Text>
          )}
          {metrics?.memory && (
            <Text size="sm" c="dimmed">
              <IconDeviceDesktop size={14} style={{ verticalAlign: "middle" }} />{" "}
              RAM: {metrics.memory.percent_used}%
            </Text>
          )}
          {metrics?.gpu && (
            <Text size="sm" c="dimmed">
              GPU: {metrics.gpu.utilization_percent}% · {metrics.gpu.temperature_c}°C
            </Text>
          )}
        </Group>
      </Paper>

      {/* ── Recent Runs ──────────────────────────── */}
      <Paper p="md" radius="md" withBorder>
        <Text fw={600} mb="xs">Runs récents</Text>
        {recentRuns.length === 0 ? (
          <Text size="sm" c="dimmed">Aucun run pour le moment.</Text>
        ) : (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Goal</Table.Th>
                <Table.Th>Score</Table.Th>
                <Table.Th>Statut</Table.Th>
                <Table.Th>Créé</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {recentRuns.map((r: Run) => (
                <Table.Tr key={r.id}>
                  <Table.Td><Text size="xs" ff="monospace">{r.id}</Text></Table.Td>
                  <Table.Td><Text size="xs" ff="monospace">{r.goal_id}</Text></Table.Td>
                  <Table.Td>{r.score > 0 ? r.score.toFixed(2) : "—"}</Table.Td>
                  <Table.Td><Badge size="xs" color={statusColor(r.status)}>{r.status}</Badge></Table.Td>
                  <Table.Td><Text size="xs" c="dimmed">{timeAgo(r.created_at)}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* ── Recent Jobs ──────────────────────────── */}
      <Paper p="md" radius="md" withBorder>
        <Text fw={600} mb="xs">Jobs récents</Text>
        {recentJobs.length === 0 ? (
          <Text size="sm" c="dimmed">Aucun job pour le moment.</Text>
        ) : (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Statut</Table.Th>
                <Table.Th>Worker</Table.Th>
                <Table.Th>Créé</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {recentJobs.map((j: Job) => (
                <Table.Tr key={j.id}>
                  <Table.Td><Text size="xs" ff="monospace">{j.id}</Text></Table.Td>
                  <Table.Td><Badge size="xs" variant="light">{j.job_type}</Badge></Table.Td>
                  <Table.Td><Badge size="xs" color={statusColor(j.status)}>{j.status}</Badge></Table.Td>
                  <Table.Td><Text size="xs" c="dimmed">{j.worker_id || "—"}</Text></Table.Td>
                  <Table.Td><Text size="xs" c="dimmed">{timeAgo(j.created_at)}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* ── Live Events ──────────────────────────── */}
      {events.length > 0 && (
        <Paper p="md" radius="md" withBorder>
          <Text fw={600} mb="xs">Événements live</Text>
          <Stack gap={4}>
            {events.slice(0, 8).map((e, i) => (
              <Text key={i} size="xs" ff="monospace" c="dimmed">
                [{new Date(e.timestamp * 1000).toLocaleTimeString()}]{" "}
                <Text span c="violet" inherit>{e.type}</Text>{" "}
                {JSON.stringify(e.data)}
              </Text>
            ))}
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}

function HealthBadge({ label, ok }: { label: string; ok?: boolean }) {
  return (
    <Badge
      variant="dot"
      color={ok === undefined ? "gray" : ok ? "green" : "red"}
      size="sm"
    >
      {label}
    </Badge>
  );
}
