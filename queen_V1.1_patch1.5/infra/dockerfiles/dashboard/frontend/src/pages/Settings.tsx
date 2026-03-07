/**
 * Settings.tsx — Configuration (read-only), métriques détaillées, logs.
 */

import {
  Title, Paper, Text, Stack, Group, Badge, Loader, Table,
  Progress, Grid, Box, Divider, Code,
} from "@mantine/core";
import {
  IconCpu, IconDeviceDesktop, IconDeviceSdCard,
  IconBrandOpenai, IconServer,
} from "@tabler/icons-react";
import { useSettings, useHealth, useMetrics } from "../api/hooks";
import LogPanel from "../components/LogPanel";

export default function Settings() {
  const { data: settings, isLoading: loadS } = useSettings();
  const { data: health } = useHealth();
  const { data: metrics } = useMetrics();

  if (loadS) return <Loader m="xl" />;

  return (
    <Stack gap="lg">
      <Title order={2}>Settings</Title>

      <Grid>
        {/* ── LLM Config ──────────────────────── */}
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Paper p="md" radius="md" withBorder h="100%">
            <Group gap={6} mb="sm">
              <IconBrandOpenai size={18} />
              <Text fw={600} size="sm">LLM Configuration</Text>
            </Group>
            <ConfigTable
              rows={[
                ["Provider", settings?.llm_provider ?? "—"],
                ["Ollama Model", settings?.ollama_model ?? "—"],
                ["Ollama URL", settings?.ollama_url ?? "—"],
                ["OpenAI Model", settings?.openai_model ?? "—"],
                [
                  "Statut",
                  health?.components?.llm?.status === "ok"
                    ? "✅ Connecté"
                    : "❌ Indisponible",
                ],
              ]}
            />
          </Paper>
        </Grid.Col>

        {/* ── Policy Config ───────────────────── */}
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Paper p="md" radius="md" withBorder h="100%">
            <Group gap={6} mb="sm">
              <IconServer size={18} />
              <Text fw={600} size="sm">Politique & Budgets</Text>
            </Group>
            <ConfigTable
              rows={[
                ["Timeout par job", `${settings?.policy_job_timeout ?? 300}s`],
                ["Timeout max", `${settings?.policy_max_job_timeout ?? 1800}s`],
                ["Output max", formatBytes(settings?.policy_max_output_bytes ?? 0)],
                ["Jobs max / run", String(settings?.policy_max_jobs_per_run ?? 20)],
                ["Jobs concurrents", String(settings?.policy_max_concurrent_jobs ?? 5)],
                [
                  "Approbation manuelle",
                  settings?.require_manual_approval ? "✅ Oui" : "❌ Non",
                ],
              ]}
            />
          </Paper>
        </Grid.Col>
      </Grid>

      {/* ── System Metrics ────────────────────── */}
      <Paper p="md" radius="md" withBorder>
        <Text fw={600} size="sm" mb="sm">Métriques Système</Text>
        <Grid>
          {metrics?.cpu && (
            <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
              <MetricCard
                icon={<IconCpu size={16} />}
                label="CPU Load"
                value={`${metrics.cpu.load_1m.toFixed(2)} / ${metrics.cpu.load_5m.toFixed(2)} / ${metrics.cpu.load_15m.toFixed(2)}`}
                sub="1m / 5m / 15m"
              />
            </Grid.Col>
          )}

          {metrics?.memory && (
            <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
              <MetricCard
                icon={<IconDeviceDesktop size={16} />}
                label="RAM"
                value={`${metrics.memory.used_mb} / ${metrics.memory.total_mb} MB`}
                percent={metrics.memory.percent_used}
              />
            </Grid.Col>
          )}

          {metrics?.disk && (
            <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
              <MetricCard
                icon={<IconDeviceSdCard size={16} />}
                label="Disque /data"
                value={`${metrics.disk.used_gb} / ${metrics.disk.total_gb} GB`}
                percent={metrics.disk.percent_used}
              />
            </Grid.Col>
          )}

          {metrics?.gpu && (
            <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
              <MetricCard
                icon={<IconCpu size={16} />}
                label={metrics.gpu.name}
                value={`${metrics.gpu.memory_used_mb} / ${metrics.gpu.memory_total_mb} MB`}
                percent={metrics.gpu.utilization_percent}
                sub={`${metrics.gpu.temperature_c}°C`}
              />
            </Grid.Col>
          )}

          {!metrics?.cpu && !metrics?.memory && !metrics?.disk && !metrics?.gpu && (
            <Grid.Col span={12}>
              <Text size="sm" c="dimmed">Métriques indisponibles.</Text>
            </Grid.Col>
          )}
        </Grid>
      </Paper>

      {/* ── Health Detail ─────────────────────── */}
      <Paper p="md" radius="md" withBorder>
        <Text fw={600} size="sm" mb="sm">Santé des composants</Text>
        <Group gap="lg">
          {health?.components &&
            Object.entries(health.components).map(([name, comp]) => {
              const c = comp as Record<string, unknown>;
              const ok = c.status === "ok";
              const queueLength = typeof c.queue_length === "number" ? c.queue_length : undefined;
              const provider = typeof c.provider === "string" ? c.provider : undefined;
              const errorMsg = typeof c.error === "string" ? c.error : undefined;
              return (
                <Paper key={name} p="sm" radius="sm" withBorder>
                  <Group gap={6}>
                    <Badge variant="dot" color={ok ? "green" : "red"} size="sm">
                      {name}
                    </Badge>
                  </Group>
                  {queueLength !== undefined && (
                    <Text size="xs" c="dimmed" mt={4}>
                      Queue: {queueLength} jobs
                    </Text>
                  )}
                  {provider && (
                    <Text size="xs" c="dimmed" mt={4}>
                      Provider: {provider}
                    </Text>
                  )}
                  {errorMsg && (
                    <Text size="xs" c="red" mt={4}>
                      {errorMsg}
                    </Text>
                  )}
                </Paper>
              );
            })}
        </Group>
      </Paper>

      {/* ── Logs ──────────────────────────────── */}
      <LogPanel maxHeight={450} />
    </Stack>
  );
}

/* ── Helper components ──────────────────────────────────────── */

function ConfigTable({ rows }: { rows: [string, string][] }) {
  return (
    <Table>
      <Table.Tbody>
        {rows.map(([k, v]) => (
          <Table.Tr key={k}>
            <Table.Td w="45%">
              <Text size="xs" c="dimmed">{k}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="sm" ff="monospace">{v}</Text>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function MetricCard({
  icon, label, value, percent, sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  percent?: number;
  sub?: string;
}) {
  const color = percent !== undefined
    ? percent > 85 ? "red" : percent > 60 ? "yellow" : "green"
    : "violet";

  return (
    <Paper p="sm" radius="sm" withBorder>
      <Group gap={6} mb={4}>
        {icon}
        <Text size="xs" fw={600}>{label}</Text>
      </Group>
      <Text size="sm" ff="monospace">{value}</Text>
      {percent !== undefined && (
        <Progress value={percent} color={color} size="xs" mt={6} radius="xl" />
      )}
      {sub && <Text size="xs" c="dimmed" mt={2}>{sub}</Text>}
    </Paper>
  );
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(0)} MB`;
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(0)} KB`;
  return `${bytes} B`;
}
