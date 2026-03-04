/**
 * Shell.tsx — Layout principal : sidebar + contenu.
 * Mantine AppShell, navigation via React Router.
 */

import { AppShell, NavLink, Title, Text, Badge, Group, Box } from "@mantine/core";
import {
  IconLayoutDashboard,
  IconTarget,
  IconRefresh,
  IconBolt,
  IconGitPullRequest,
  IconSettings,
} from "@tabler/icons-react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useHealth } from "../api/hooks";
import { useEvents } from "../ws/useEvents";

const NAV = [
  { label: "Overview", icon: IconLayoutDashboard, path: "/" },
  { label: "Goals", icon: IconTarget, path: "/goals" },
  { label: "Runs", icon: IconRefresh, path: "/runs" },
  { label: "Patches", icon: IconGitPullRequest, path: "/patches" },
  { label: "Settings", icon: IconSettings, path: "/settings" },
];

export default function Shell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: health } = useHealth();
  const { connected } = useEvents();

  const systemOk = health?.status === "ok";

  return (
    <AppShell
      navbar={{ width: 220, breakpoint: "sm" }}
      padding="md"
      styles={{
        main: { backgroundColor: "var(--mantine-color-dark-8)" },
        navbar: { backgroundColor: "var(--mantine-color-dark-7)", borderRight: "1px solid var(--mantine-color-dark-5)" },
      }}
    >
      <AppShell.Navbar p="xs">
        <Box mb="md" px="xs">
          <Title order={4}>🐝 Queen V1</Title>
          <Group gap={6} mt={4}>
            <Badge
              size="xs"
              variant="dot"
              color={systemOk ? "green" : "red"}
            >
              {systemOk ? "système OK" : "dégradé"}
            </Badge>
            <Badge
              size="xs"
              variant="dot"
              color={connected ? "green" : "gray"}
            >
              {connected ? "live" : "offline"}
            </Badge>
          </Group>
        </Box>

        {NAV.map((item) => (
          <NavLink
            key={item.path}
            label={item.label}
            leftSection={<item.icon size={18} />}
            active={
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path)
            }
            onClick={() => navigate(item.path)}
            styles={{
              root: { borderRadius: 6, marginBottom: 2 },
            }}
          />
        ))}

        <Box mt="auto" px="xs" pb="xs">
          <Text size="xs" c="dimmed">
            Dashboard local — v1.0
          </Text>
        </Box>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
