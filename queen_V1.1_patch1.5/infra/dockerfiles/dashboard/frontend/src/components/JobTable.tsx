/**
 * JobTable.tsx — Tableau détaillé des jobs avec actions retry/cancel
 * et logs expansibles.
 */

import { useState } from "react";
import {
  Table, Badge, Text, Group, ActionIcon, Tooltip, Collapse,
  Paper, Code, Box,
} from "@mantine/core";
import {
  IconRefresh, IconPlayerStop, IconChevronDown, IconChevronRight,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { useRetryJob, useCancelJob } from "../api/hooks";
import type { Job } from "../api/types";

function statusColor(s: string): string {
  if (s === "success") return "green";
  if (["failed", "timeout"].includes(s)) return "red";
  if (s === "running") return "blue";
  if (s === "queued") return "violet";
  return "gray";
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
  jobs: Job[];
}

export default function JobTable({ jobs }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const retryMut = useRetryJob();
  const cancelMut = useCancelJob();

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleRetry = (id: string) => {
    retryMut.mutate(id, {
      onSuccess: () => notifications.show({ title: "Retry", message: `Job ${id} relancé`, color: "blue" }),
      onError: (e) => notifications.show({ title: "Erreur", message: e.message, color: "red" }),
    });
  };

  const handleCancel = (id: string) => {
    cancelMut.mutate(id, {
      onSuccess: () => notifications.show({ title: "Annulé", message: `Job ${id} annulé`, color: "yellow" }),
      onError: (e) => notifications.show({ title: "Erreur", message: e.message, color: "red" }),
    });
  };

  if (!jobs.length) {
    return <Text c="dimmed" size="sm">Aucun job.</Text>;
  }

  return (
    <Table highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={30} />
          <Table.Th>ID</Table.Th>
          <Table.Th>Type</Table.Th>
          <Table.Th>Statut</Table.Th>
          <Table.Th>Durée</Table.Th>
          <Table.Th>Worker</Table.Th>
          <Table.Th>Actions</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {jobs.map((j) => {
          const isOpen = expanded.has(j.id);
          const canRetry = ["failed", "timeout", "cancelled"].includes(j.status);
          const canCancel = ["queued", "running"].includes(j.status);

          return (
            <Box key={j.id} component="tr" style={{ cursor: "pointer" }}>
              {/* Main row wrapped in fragment to allow Collapse below */}
              <Table.Td onClick={() => toggle(j.id)}>
                {isOpen ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
              </Table.Td>
              <Table.Td onClick={() => toggle(j.id)}>
                <Text size="xs" ff="monospace">{j.id}</Text>
              </Table.Td>
              <Table.Td>
                <Badge size="xs" variant="light">{j.job_type}</Badge>
              </Table.Td>
              <Table.Td>
                <Badge size="xs" color={statusColor(j.status)}>{j.status}</Badge>
              </Table.Td>
              <Table.Td>
                <Text size="xs" ff="monospace">{duration(j.started_at, j.finished_at)}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="xs" c="dimmed">{j.worker_id || "—"}</Text>
              </Table.Td>
              <Table.Td>
                <Group gap={4}>
                  {canRetry && (
                    <Tooltip label="Retry">
                      <ActionIcon
                        variant="subtle" color="blue" size="sm"
                        loading={retryMut.isPending}
                        onClick={(e) => { e.stopPropagation(); handleRetry(j.id); }}
                      >
                        <IconRefresh size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  {canCancel && (
                    <Tooltip label="Annuler">
                      <ActionIcon
                        variant="subtle" color="red" size="sm"
                        loading={cancelMut.isPending}
                        onClick={(e) => { e.stopPropagation(); handleCancel(j.id); }}
                      >
                        <IconPlayerStop size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                </Group>
              </Table.Td>
            </Box>
          );
        })}
      </Table.Tbody>

      {/* Expanded details rendered outside tbody to avoid nesting issues */}
      {jobs.map((j) =>
        expanded.has(j.id) ? (
          <Table.Tbody key={`${j.id}-detail`}>
            <Table.Tr>
              <Table.Td colSpan={7} p={0}>
                <JobDetail job={j} />
              </Table.Td>
            </Table.Tr>
          </Table.Tbody>
        ) : null
      )}
    </Table>
  );
}

function JobDetail({ job }: { job: Job }) {
  const payload =
    job.payload && typeof job.payload === "object"
      ? (job.payload as Record<string, unknown>)
      : {};
  const result =
    job.result && typeof job.result === "object"
      ? (job.result as Record<string, unknown>)
      : {};

  const title = typeof payload.title === "string" ? payload.title : undefined;
  const description = typeof payload.description === "string" ? payload.description : undefined;

  return (
    <Paper p="sm" m="xs" radius="sm" bg="var(--mantine-color-dark-7)">
      {title && (
        <Text size="sm" fw={500} mb={4}>{title}</Text>
      )}
      {description && (
        <Text size="xs" c="dimmed" mb="xs">{description}</Text>
      )}

      {job.logs && (
        <Box mb="xs">
          <Text size="xs" fw={600} mb={2}>Logs</Text>
          <Code block style={{ maxHeight: 150, overflow: "auto", fontSize: 11 }}>
            {String(job.logs)}
          </Code>
        </Box>
      )}

      {Object.keys(result).length > 0 && (
        <Box>
          <Text size="xs" fw={600} mb={2}>Résultat</Text>
          <Code block style={{ maxHeight: 200, overflow: "auto", fontSize: 11 }}>
            {JSON.stringify(result, null, 2)}
          </Code>
        </Box>
      )}
    </Paper>
  );
}
