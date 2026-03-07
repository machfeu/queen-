/**
 * Goals.tsx — Liste des objectifs + actions pause/resume.
 * Le formulaire de création est dans un composant séparé (GoalCreateModal).
 */

import { useState } from "react";
import {
  Title, Paper, Table, Badge, Group, Button, Text, Stack,
  Loader, ActionIcon, Tooltip,
} from "@mantine/core";
import {
  IconPlus, IconPlayerPause, IconPlayerPlay, IconEye,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { useNavigate } from "react-router-dom";
import { useGoals, usePauseGoal, useResumeGoal } from "../api/hooks";
import GoalCreateModal from "../components/GoalCreateModal";
import type { Goal } from "../api/types";

function statusColor(s: string): string {
  if (["completed"].includes(s)) return "green";
  if (["failed"].includes(s)) return "red";
  if (["running"].includes(s)) return "blue";
  if (["paused"].includes(s)) return "yellow";
  if (["planning"].includes(s)) return "violet";
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

export default function Goals() {
  const [createOpen, setCreateOpen] = useState(false);
  const { data: goals, isLoading } = useGoals();
  const pauseMut = usePauseGoal();
  const resumeMut = useResumeGoal();
  const navigate = useNavigate();

  const handlePause = (id: string) => {
    pauseMut.mutate(id, {
      onSuccess: () => notifications.show({ title: "Pause", message: `Goal ${id} mis en pause`, color: "yellow" }),
      onError: (e) => notifications.show({ title: "Erreur", message: e.message, color: "red" }),
    });
  };

  const handleResume = (id: string) => {
    resumeMut.mutate(id, {
      onSuccess: () => notifications.show({ title: "Reprise", message: `Goal ${id} relancé`, color: "green" }),
      onError: (e) => notifications.show({ title: "Erreur", message: e.message, color: "red" }),
    });
  };

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Goals</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
          Nouvel objectif
        </Button>
      </Group>

      <GoalCreateModal opened={createOpen} onClose={() => setCreateOpen(false)} />

      <Paper p="md" radius="md" withBorder>
        {isLoading ? (
          <Loader m="xl" />
        ) : !goals || goals.length === 0 ? (
          <Text c="dimmed" ta="center" py="xl">
            Aucun objectif. Cliquez sur « Nouvel objectif » pour commencer.
          </Text>
        ) : (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Titre</Table.Th>
                <Table.Th>Statut</Table.Th>
                <Table.Th>Risque</Table.Th>
                <Table.Th>Créé</Table.Th>
                <Table.Th>Actions</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {goals.map((g: Goal) => (
                <Table.Tr key={g.id}>
                  <Table.Td>
                    <Text size="xs" ff="monospace">{g.id}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={500} lineClamp={1}>{g.title}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" color={statusColor(g.status)}>{g.status}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">
                      {(g.constraints as Record<string, string>)?.risk_level ?? "—"}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">{timeAgo(g.created_at)}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      <Tooltip label="Voir les runs">
                        <ActionIcon
                          variant="subtle" size="sm"
                          onClick={() => navigate(`/runs?goal=${g.id}`)}
                        >
                          <IconEye size={14} />
                        </ActionIcon>
                      </Tooltip>

                      {g.status === "running" && (
                        <Tooltip label="Pause">
                          <ActionIcon
                            variant="subtle" color="yellow" size="sm"
                            loading={pauseMut.isPending}
                            onClick={() => handlePause(g.id)}
                          >
                            <IconPlayerPause size={14} />
                          </ActionIcon>
                        </Tooltip>
                      )}

                      {g.status === "paused" && (
                        <Tooltip label="Reprendre">
                          <ActionIcon
                            variant="subtle" color="green" size="sm"
                            loading={resumeMut.isPending}
                            onClick={() => handleResume(g.id)}
                          >
                            <IconPlayerPlay size={14} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
    </Stack>
  );
}
