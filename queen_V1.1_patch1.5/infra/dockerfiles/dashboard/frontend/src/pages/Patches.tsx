/**
 * Patches.tsx — Liste des patches + ouverture du diff modal.
 */

import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Title, Paper, Table, Badge, Text, Stack, Loader, Group,
  ActionIcon, Tooltip,
} from "@mantine/core";
import { IconEye, IconCheck, IconX, IconShieldCheck } from "@tabler/icons-react";
import { usePatches, usePatchDiff } from "../api/hooks";
import PatchDiffModal from "../components/PatchDiffModal";
import type { Patch, GateResult } from "../api/types";

function statusColor(s: string): string {
  if (["applied", "gates_passed", "approved"].includes(s)) return "green";
  if (["gates_failed", "rejected", "rolled_back"].includes(s)) return "red";
  if (["gates_running", "generated"].includes(s)) return "blue";
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

function gatesSummary(gates: Record<string, GateResult>): { passed: number; total: number } {
  const entries = Object.values(gates);
  return {
    total: entries.length,
    passed: entries.filter((g) => (g as GateResult).passed).length,
  };
}

export default function Patches() {
  const [params] = useSearchParams();
  const highlight = params.get("highlight") ?? undefined;
  const { data: patchList, isLoading } = usePatches();

  const [selected, setSelected] = useState<Patch | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  // Fetch diff only when a patch is selected
  const { data: diffData } = usePatchDiff(selected?.id ?? "");
  const diffContent = diffData?.diff ?? "";

  // Auto-open highlighted patch
  useEffect(() => {
    if (highlight && patchList) {
      const found = patchList.find((p) => p.id === highlight);
      if (found) {
        setSelected(found);
        setModalOpen(true);
      }
    }
  }, [highlight, patchList]);

  const openPatch = (p: Patch) => {
    setSelected(p);
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setSelected(null);
  };

  return (
    <Stack gap="lg">
      <Title order={2}>Patches</Title>

      <PatchDiffModal
        patch={selected}
        diff={diffContent}
        opened={modalOpen}
        onClose={closeModal}
      />

      <Paper p="md" radius="md" withBorder>
        {isLoading ? (
          <Loader m="xl" />
        ) : !patchList || patchList.length === 0 ? (
          <Text c="dimmed" ta="center" py="xl">
            Aucun patch généré pour le moment.
          </Text>
        ) : (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Run</Table.Th>
                <Table.Th>Goal</Table.Th>
                <Table.Th>Gates</Table.Th>
                <Table.Th>Statut</Table.Th>
                <Table.Th>Créé</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {patchList.map((p: Patch) => {
                const gates = gatesSummary(
                  (p.gate_results ?? {}) as Record<string, GateResult>
                );
                const isHighlighted = p.id === highlight;

                return (
                  <Table.Tr
                    key={p.id}
                    style={{
                      cursor: "pointer",
                      background: isHighlighted
                        ? "var(--mantine-color-violet-light)"
                        : undefined,
                    }}
                    onClick={() => openPatch(p)}
                  >
                    <Table.Td>
                      <Text size="xs" ff="monospace">{p.id}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" ff="monospace">{p.run_id}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" ff="monospace">{p.goal_id}</Text>
                    </Table.Td>
                    <Table.Td>
                      {gates.total > 0 ? (
                        <Group gap={4}>
                          <IconShieldCheck
                            size={14}
                            color={
                              gates.passed === gates.total
                                ? "var(--mantine-color-green-5)"
                                : "var(--mantine-color-red-5)"
                            }
                          />
                          <Text size="xs">
                            {gates.passed}/{gates.total}
                          </Text>
                        </Group>
                      ) : (
                        <Text size="xs" c="dimmed">—</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Badge size="xs" color={statusColor(p.status)}>
                        {p.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text size="xs" c="dimmed">{timeAgo(p.created_at)}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Tooltip label="Voir le diff">
                        <ActionIcon
                          variant="subtle" size="sm"
                          onClick={(e) => { e.stopPropagation(); openPatch(p); }}
                        >
                          <IconEye size={14} />
                        </ActionIcon>
                      </Tooltip>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
    </Stack>
  );
}
