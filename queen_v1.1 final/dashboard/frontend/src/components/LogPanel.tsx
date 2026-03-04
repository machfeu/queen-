/**
 * LogPanel.tsx — Panneau de logs temps réel avec filtrage par niveau.
 */

import { useState, useRef, useEffect } from "react";
import {
  Paper, Text, Group, SegmentedControl, Box, Badge, ActionIcon,
  Tooltip, Stack,
} from "@mantine/core";
import { IconArrowDown, IconTrash } from "@tabler/icons-react";
import { useLogs } from "../api/hooks";
import type { LogEntry } from "../api/types";

const LEVEL_COLORS: Record<string, string> = {
  error: "var(--mantine-color-red-5)",
  warn: "var(--mantine-color-yellow-5)",
  info: "var(--mantine-color-dimmed)",
  debug: "var(--mantine-color-dark-3)",
};

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

interface Props {
  maxHeight?: number;
}

export default function LogPanel({ maxHeight = 350 }: Props) {
  const [filter, setFilter] = useState("all");
  const [autoScroll, setAutoScroll] = useState(true);
  const { data: logs } = useLogs(200);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = (logs ?? []).filter((l: LogEntry) => {
    if (filter === "all") return true;
    return l.level === filter;
  });

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [filtered.length, autoScroll]);

  return (
    <Paper p="md" radius="md" withBorder>
      <Group justify="space-between" mb="xs">
        <Text fw={600} size="sm">Logs</Text>
        <Group gap="xs">
          <SegmentedControl
            size="xs"
            value={filter}
            onChange={setFilter}
            data={[
              { label: "Tous", value: "all" },
              { label: "Info", value: "info" },
              { label: "Warn", value: "warn" },
              { label: "Error", value: "error" },
            ]}
          />
          <Tooltip label={autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}>
            <ActionIcon
              variant={autoScroll ? "filled" : "subtle"}
              size="sm"
              color="violet"
              onClick={() => setAutoScroll(!autoScroll)}
            >
              <IconArrowDown size={14} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <Box
        ref={scrollRef}
        style={{
          maxHeight,
          overflowY: "auto",
          fontFamily: "'Fira Code', 'Cascadia Code', monospace",
          fontSize: 11,
          lineHeight: 1.7,
          background: "var(--mantine-color-dark-8)",
          borderRadius: 6,
          padding: "8px 10px",
        }}
      >
        {filtered.length === 0 ? (
          <Text size="xs" c="dimmed" ta="center" py="md">
            Aucun log.
          </Text>
        ) : (
          filtered.map((log: LogEntry, i: number) => (
            <div key={i} style={{ display: "flex", gap: 8 }}>
              <span style={{ color: "var(--mantine-color-dark-3)", flexShrink: 0 }}>
                {formatTs(log.timestamp)}
              </span>
              <span
                style={{
                  color: LEVEL_COLORS[log.level] ?? LEVEL_COLORS.info,
                  flexShrink: 0,
                  width: 38,
                  textTransform: "uppercase",
                  fontWeight: log.level === "error" ? 700 : 400,
                }}
              >
                {log.level}
              </span>
              <span style={{ color: "var(--mantine-color-violet-4)", flexShrink: 0 }}>
                [{log.source}]
              </span>
              <span style={{ color: "var(--mantine-color-gray-4)", wordBreak: "break-all" }}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </Box>

      <Text size="xs" c="dimmed" mt={4} ta="right">
        {filtered.length} entrée{filtered.length > 1 ? "s" : ""}
      </Text>
    </Paper>
  );
}
