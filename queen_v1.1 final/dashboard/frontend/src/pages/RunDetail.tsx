/**
 * RunDetail.tsx — Détail d'un run : info, score, timeline, jobs, lien patch.
 * Accessible via /runs/:runId
 */

import { useParams, useNavigate } from "react-router-dom";
import {
  Title, Text, Paper, Group, Badge, Stack, Loader, Button,
  Progress, Grid, Box,
} from "@mantine/core";
import { IconArrowLeft, IconGitPullRequest } from "@tabler/icons-react";
import { useRun, useRunTimeline, useJobs } from "../api/hooks";
import Timeline from "../components/Timeline";
import JobTable from "../components/JobTable";

function statusColor(s: string): string {
  if (["applied", "gates_passed", "approved"].includes(s)) return "green";
  if (["gates_failed", "rejected", "rolled_back"].includes(s)) return "red";
  if (["running", "gates_pending", "gates_running"].includes(s)) return "blue";
  return "gray";
}

export default function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { data: run, isLoading: loadRun } = useRun(runId ?? "");
  const { data: timeline, isLoading: loadTl } = useRunTimeline(runId ?? "");
  const { data: jobs } = useJobs({ run_id: runId });

  if (loadRun || loadTl) return <Loader m="xl" />;
  if (!run) {
    return (
      <Stack gap="md">
        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate(-1)}>
          Retour
        </Button>
        <Text c="dimmed">Run introuvable.</Text>
      </Stack>
    );
  }

  const score = run.score ?? 0;
  const scorePercent = Math.round(score * 100);
  const scoreColor = score > 0.7 ? "green" : score > 0.3 ? "yellow" : "red";

  return (
    <Stack gap="lg">
      {/* Header */}
      <Group justify="space-between">
        <Group gap="sm">
          <Button variant="subtle" size="xs" leftSection={<IconArrowLeft size={14} />} onClick={() => navigate(-1)}>
            Retour
          </Button>
          <Title order={3}>Run {run.id}</Title>
          <Badge color={statusColor(run.status)} size="md">{run.status}</Badge>
        </Group>
        {run.patch_id && (
          <Button
            variant="light"
            size="xs"
            leftSection={<IconGitPullRequest size={14} />}
            onClick={() => navigate(`/patches?highlight=${run.patch_id}`)}
          >
            Voir le patch
          </Button>
        )}
      </Group>

      {/* Score + Info */}
      <Grid>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Paper p="md" radius="md" withBorder>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={4}>Score</Text>
            <Group gap="sm" align="flex-end">
              <Text size="xl" fw={700} c={scoreColor}>
                {score > 0 ? score.toFixed(2) : "—"}
              </Text>
              {score > 0 && (
                <Text size="xs" c="dimmed">/ 1.0</Text>
              )}
            </Group>
            {score > 0 && (
              <Progress value={scorePercent} color={scoreColor} size="sm" mt="xs" radius="xl" />
            )}
          </Paper>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Paper p="md" radius="md" withBorder>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={4}>Goal</Text>
            <Text size="sm" ff="monospace">{run.goal_id}</Text>
          </Paper>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Paper p="md" radius="md" withBorder>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={4}>Jobs</Text>
            <Text size="sm">
              {jobs?.filter((j) => j.status === "success").length ?? 0} /{" "}
              {jobs?.length ?? 0} réussis
            </Text>
          </Paper>
        </Grid.Col>
      </Grid>

      {/* Timeline */}
      <Paper p="md" radius="md" withBorder>
        <Text fw={600} mb="sm">Timeline</Text>
        <Timeline items={timeline?.timeline ?? []} />
      </Paper>

      {/* Job Table */}
      <Paper p="md" radius="md" withBorder>
        <Text fw={600} mb="sm">Jobs détaillés</Text>
        <JobTable jobs={jobs ?? []} />
      </Paper>

      {/* Score justification */}
      {run.score_justification && (
        <Paper p="md" radius="md" withBorder>
          <Text fw={600} mb="sm">Justification du score</Text>
          <ScoreJustification raw={run.score_justification} />
        </Paper>
      )}
    </Stack>
  );
}

function ScoreJustification({ raw }: { raw: string }) {
  try {
    const data = JSON.parse(raw);
    return (
      <Stack gap="xs">
        {data.justification && (
          <Text size="sm">{data.justification}</Text>
        )}
        {data.criteria && (
          <Group gap="md" mt="xs">
            {Object.entries(data.criteria as Record<string, number>).map(([k, v]) => (
              <Box key={k}>
                <Text size="xs" c="dimmed" tt="capitalize">{k}</Text>
                <Progress
                  value={Math.round((v as number) * 100)}
                  color={v > 0.7 ? "green" : v > 0.3 ? "yellow" : "red"}
                  size="sm"
                  w={100}
                  radius="xl"
                />
                <Text size="xs" ta="center">{(v as number).toFixed(2)}</Text>
              </Box>
            ))}
          </Group>
        )}
        {data.verdict && (
          <Badge
            mt="xs"
            color={data.verdict === "approve" ? "green" : data.verdict === "retry" ? "yellow" : "red"}
          >
            Verdict : {data.verdict}
          </Badge>
        )}
      </Stack>
    );
  } catch {
    return <Text size="sm" c="dimmed">{raw}</Text>;
  }
}
