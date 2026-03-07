/**
 * Runs.tsx — Liste des runs avec lien vers le détail.
 */

import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Title, Paper, Table, Badge, Text, Stack, Loader, Group,
  Progress,
} from "@mantine/core";
import { useRuns } from "../api/hooks";
import type { Run } from "../api/types";

function statusColor(s: string): string {
  if (["applied", "gates_passed", "approved"].includes(s)) return "green";
  if (["gates_failed", "rejected", "rolled_back"].includes(s)) return "red";
  if (["running", "gates_pending"].includes(s)) return "blue";
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

export default function Runs() {
  const [params] = useSearchParams();
  const goalFilter = params.get("goal") ?? undefined;
  const { data: runs, isLoading } = useRuns(goalFilter);
  const navigate = useNavigate();

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Runs</Title>
        {goalFilter && (
          <Badge variant="outline" size="sm">Filtre: {goalFilter}</Badge>
        )}
      </Group>

      <Paper p="md" radius="md" withBorder>
        {isLoading ? (
          <Loader m="xl" />
        ) : !runs || runs.length === 0 ? (
          <Text c="dimmed" ta="center" py="xl">Aucun run.</Text>
        ) : (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>ID</Table.Th>
                <Table.Th>Goal</Table.Th>
                <Table.Th>Score</Table.Th>
                <Table.Th>Statut</Table.Th>
                <Table.Th>Patch</Table.Th>
                <Table.Th>Créé</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {runs.map((r: Run) => (
                <Table.Tr
                  key={r.id}
                  style={{ cursor: "pointer" }}
                  onClick={() => navigate(`/runs/${r.id}`)}
                >
                  <Table.Td><Text size="xs" ff="monospace">{r.id}</Text></Table.Td>
                  <Table.Td><Text size="xs" ff="monospace">{r.goal_id}</Text></Table.Td>
                  <Table.Td>
                    {r.score > 0 ? (
                      <Group gap={6}>
                        <Progress
                          value={Math.round(r.score * 100)}
                          color={r.score > 0.7 ? "green" : r.score > 0.3 ? "yellow" : "red"}
                          size="sm" w={60} radius="xl"
                        />
                        <Text size="xs">{r.score.toFixed(2)}</Text>
                      </Group>
                    ) : (
                      <Text size="xs" c="dimmed">—</Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Badge size="xs" color={statusColor(r.status)}>{r.status}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" ff="monospace" c="dimmed">{r.patch_id || "—"}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">{timeAgo(r.created_at)}</Text>
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
