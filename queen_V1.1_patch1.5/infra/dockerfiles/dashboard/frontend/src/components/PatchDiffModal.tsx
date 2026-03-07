/**
 * PatchDiffModal.tsx — Affiche le diff d'un patch + résultats des gates
 * + boutons approve/apply/reject/rollback.
 */

import {
  Modal, Text, Badge, Group, Stack, Paper, Button, Code,
  Divider, Box, ThemeIcon, List,
} from "@mantine/core";
import {
  IconCheck, IconX, IconPlayerPlay, IconArrowBackUp,
  IconShieldCheck,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import {
  useApprovePatch, useApplyPatch, useRejectPatch, useRollbackPatch,
} from "../api/hooks";
import type { Patch, GateResult } from "../api/types";

interface Props {
  patch: Patch | null;
  diff: string;
  opened: boolean;
  onClose: () => void;
}

function statusColor(s: string): string {
  if (["applied", "gates_passed", "approved"].includes(s)) return "green";
  if (["gates_failed", "rejected", "rolled_back"].includes(s)) return "red";
  if (["gates_running"].includes(s)) return "blue";
  return "gray";
}

export default function PatchDiffModal({ patch, diff, opened, onClose }: Props) {
  const approveMut = useApprovePatch();
  const applyMut = useApplyPatch();
  const rejectMut = useRejectPatch();
  const rollbackMut = useRollbackPatch();

  if (!patch) return null;

  const gates = patch.gate_results ?? {};
  const allGatesPassed = Object.values(gates).every((g) => (g as GateResult).passed);

  const notify = (title: string, msg: string, color: string) =>
    notifications.show({ title, message: msg, color });

  const handleApprove = () =>
    approveMut.mutate(patch.id, {
      onSuccess: () => { notify("Approuvé", `Patch ${patch.id}`, "green"); onClose(); },
      onError: (e) => notify("Erreur", e.message, "red"),
    });

  const handleApply = () =>
    applyMut.mutate(patch.id, {
      onSuccess: () => { notify("Appliqué", `Patch ${patch.id} intégré au workspace`, "green"); onClose(); },
      onError: (e) => notify("Erreur", e.message, "red"),
    });

  const handleReject = () =>
    rejectMut.mutate({ id: patch.id }, {
      onSuccess: () => { notify("Rejeté", `Patch ${patch.id}`, "orange"); onClose(); },
      onError: (e) => notify("Erreur", e.message, "red"),
    });

  const handleRollback = () =>
    rollbackMut.mutate(patch.id, {
      onSuccess: () => { notify("Rollback", `Patch ${patch.id} annulé`, "yellow"); onClose(); },
      onError: (e) => notify("Erreur", e.message, "red"),
    });

  const anyLoading =
    approveMut.isPending || applyMut.isPending ||
    rejectMut.isPending || rollbackMut.isPending;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={`Patch ${patch.id}`}
      size="xl"
      centered
      styles={{ body: { maxHeight: "80vh", overflowY: "auto" } }}
    >
      <Stack gap="md">
        {/* Header info */}
        <Group justify="space-between">
          <Group gap="sm">
            <Badge color={statusColor(patch.status)} size="md">{patch.status}</Badge>
            <Text size="xs" c="dimmed">Run: {patch.run_id}</Text>
            <Text size="xs" c="dimmed">Goal: {patch.goal_id}</Text>
          </Group>
          {patch.approved_by && (
            <Text size="xs" c="dimmed">Approuvé par: {patch.approved_by}</Text>
          )}
        </Group>

        {/* Gate Results */}
        {Object.keys(gates).length > 0 && (
          <Paper p="sm" radius="sm" withBorder>
            <Group gap={6} mb="xs">
              <IconShieldCheck size={16} />
              <Text size="sm" fw={600}>Résultats des Gates</Text>
            </Group>
            <Stack gap={6}>
              {Object.entries(gates).map(([name, gate]) => {
                const g = gate as GateResult;
                return (
                  <GateRow key={name} name={name} gate={g} />
                );
              })}
            </Stack>
          </Paper>
        )}

        <Divider />

        {/* Diff viewer */}
        <Box>
          <Text size="sm" fw={600} mb="xs">Diff</Text>
          {diff ? (
            <DiffDisplay diff={diff} />
          ) : (
            <Text size="sm" c="dimmed">Aucun diff disponible.</Text>
          )}
        </Box>

        <Divider />

        {/* Actions */}
        <Group justify="flex-end" gap="sm">
          {patch.status === "gates_passed" && (
            <>
              <Button
                color="red" variant="light" size="sm"
                leftSection={<IconX size={14} />}
                onClick={handleReject}
                loading={rejectMut.isPending}
                disabled={anyLoading}
              >
                Rejeter
              </Button>
              <Button
                color="green" size="sm"
                leftSection={<IconCheck size={14} />}
                onClick={handleApprove}
                loading={approveMut.isPending}
                disabled={anyLoading || !allGatesPassed}
                title={!allGatesPassed ? "Toutes les gates doivent passer" : ""}
              >
                Approuver
              </Button>
            </>
          )}

          {patch.status === "approved" && (
            <>
              <Button
                color="red" variant="light" size="sm"
                leftSection={<IconX size={14} />}
                onClick={handleReject}
                loading={rejectMut.isPending}
                disabled={anyLoading}
              >
                Rejeter
              </Button>
              <Button
                color="blue" size="sm"
                leftSection={<IconPlayerPlay size={14} />}
                onClick={handleApply}
                loading={applyMut.isPending}
                disabled={anyLoading}
              >
                Appliquer
              </Button>
            </>
          )}

          {patch.status === "applied" && (
            <Button
              color="yellow" variant="light" size="sm"
              leftSection={<IconArrowBackUp size={14} />}
              onClick={handleRollback}
              loading={rollbackMut.isPending}
              disabled={anyLoading}
            >
              Rollback
            </Button>
          )}

          {patch.status === "gates_failed" && (
            <Text size="xs" c="red">
              ⛔ Gates échouées — patch non approuvable.
            </Text>
          )}

          {["generated", "gates_running"].includes(patch.status) && (
            <Text size="xs" c="dimmed">
              ⏳ En attente de validation des gates…
            </Text>
          )}

          {["rejected", "rolled_back"].includes(patch.status) && (
            <Text size="xs" c="dimmed">
              Ce patch a été {patch.status === "rejected" ? "rejeté" : "annulé (rollback)"}.
            </Text>
          )}
        </Group>
      </Stack>
    </Modal>
  );
}

/* ── Gate result row ────────────────────────────────────────── */

function GateRow({ name, gate }: { name: string; gate: GateResult }) {
  const issues = [
    ...(gate.violations ?? []),
    ...(gate.errors ?? []),
  ];

  return (
    <Group gap="sm" align="flex-start">
      <ThemeIcon
        size={20} radius="xl" variant="light"
        color={gate.passed ? "green" : "red"}
      >
        {gate.passed ? <IconCheck size={12} /> : <IconX size={12} />}
      </ThemeIcon>
      <Box style={{ flex: 1 }}>
        <Text size="xs" fw={500} tt="capitalize">
          {name.replace(/_/g, " ")}
        </Text>
        {issues.length > 0 && (
          <List size="xs" c="red" mt={2} spacing={0}>
            {issues.slice(0, 5).map((issue, i) => (
              <List.Item key={i}>{issue}</List.Item>
            ))}
            {issues.length > 5 && (
              <Text size="xs" c="dimmed">...et {issues.length - 5} autres</Text>
            )}
          </List>
        )}
      </Box>
    </Group>
  );
}

/* ── Diff display with syntax highlighting ──────────────────── */

function DiffDisplay({ diff }: { diff: string }) {
  const lines = diff.split("\n");

  return (
    <Code
      block
      style={{
        maxHeight: 400,
        overflowY: "auto",
        fontSize: 12,
        lineHeight: 1.5,
        whiteSpace: "pre",
        background: "var(--mantine-color-dark-8)",
      }}
    >
      {lines.map((line, i) => {
        let color = "inherit";
        if (line.startsWith("+") && !line.startsWith("+++")) color = "var(--mantine-color-green-5)";
        else if (line.startsWith("-") && !line.startsWith("---")) color = "var(--mantine-color-red-5)";
        else if (line.startsWith("@@")) color = "var(--mantine-color-violet-4)";
        else if (line.startsWith("---") || line.startsWith("+++")) color = "var(--mantine-color-blue-4)";

        return (
          <div key={i} style={{ color, minHeight: "1.4em" }}>
            {line || " "}
          </div>
        );
      })}
    </Code>
  );
}
