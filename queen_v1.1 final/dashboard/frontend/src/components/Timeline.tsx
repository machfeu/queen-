/**
 * Timeline.tsx — Vue chronologique des étapes d'un run.
 * Affiche chaque job comme un nœud avec statut, type et timing.
 */

import { Box, Text, Badge, Group, Paper, ThemeIcon } from "@mantine/core";
import {
  IconSearch, IconCode, IconTestPipe, IconChartBar,
  IconGitPullRequest, IconCircleCheck, IconCircleX,
  IconLoader2, IconClock,
} from "@tabler/icons-react";
import type { TimelineItem } from "../api/types";

const TYPE_ICON: Record<string, typeof IconSearch> = {
  research: IconSearch,
  codegen: IconCode,
  test: IconTestPipe,
  eval: IconChartBar,
  patch: IconGitPullRequest,
};

function statusColor(s: string): string {
  if (["success"].includes(s)) return "green";
  if (["failed", "timeout"].includes(s)) return "red";
  if (["running"].includes(s)) return "blue";
  if (["queued"].includes(s)) return "violet";
  return "gray";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "success") return <IconCircleCheck size={14} />;
  if (status === "failed" || status === "timeout") return <IconCircleX size={14} />;
  if (status === "running") return <IconLoader2 size={14} className="spin" />;
  return <IconClock size={14} />;
}

function duration(start: string, end: string): string {
  if (!start) return "—";
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const sec = Math.floor((e - s) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m${sec % 60}s`;
}

interface Props {
  items: TimelineItem[];
}

export default function Timeline({ items }: Props) {
  if (!items.length) {
    return <Text c="dimmed" size="sm">Aucune étape dans ce run.</Text>;
  }

  return (
    <Box
      style={{
        position: "relative",
        paddingLeft: 28,
      }}
    >
      {/* Vertical line */}
      <Box
        style={{
          position: "absolute",
          left: 11,
          top: 8,
          bottom: 8,
          width: 2,
          background: "var(--mantine-color-dark-4)",
        }}
      />

      {items.map((item, i) => {
        const Icon = TYPE_ICON[item.job_type] ?? IconCode;
        const color = statusColor(item.status);

        return (
          <Box key={item.job_id} mb="sm" style={{ position: "relative" }}>
            {/* Dot */}
            <ThemeIcon
              size={22}
              radius="xl"
              color={color}
              variant="filled"
              style={{
                position: "absolute",
                left: -28,
                top: 4,
              }}
            >
              <StatusIcon status={item.status} />
            </ThemeIcon>

            <Paper p="xs" radius="sm" withBorder>
              <Group justify="space-between" wrap="nowrap">
                <Group gap={8} wrap="nowrap">
                  <Badge size="xs" variant="light" leftSection={<Icon size={10} />}>
                    {item.job_type}
                  </Badge>
                  <Text size="sm" fw={500} lineClamp={1}>
                    {item.title || `Step ${item.step}`}
                  </Text>
                </Group>
                <Group gap={8} wrap="nowrap">
                  <Text size="xs" c="dimmed" ff="monospace">
                    {duration(item.started_at, item.finished_at)}
                  </Text>
                  <Badge size="xs" color={color}>{item.status}</Badge>
                </Group>
              </Group>
              {item.worker_id && (
                <Text size="xs" c="dimmed" mt={2}>
                  worker: {item.worker_id}
                </Text>
              )}
            </Paper>
          </Box>
        );
      })}

      {/* Spin animation for running items */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 1.2s linear infinite; }
      `}</style>
    </Box>
  );
}
