/**
 * StatCards.tsx — Grille de cartes statistiques.
 */

import { SimpleGrid, Paper, Text, Group, ThemeIcon } from "@mantine/core";
import type { ReactNode } from "react";

interface StatItem {
  label: string;
  value: string | number;
  icon: ReactNode;
  color: string;
}

export default function StatCards({ items }: { items: StatItem[] }) {
  return (
    <SimpleGrid cols={{ base: 2, sm: 3, lg: 4 }} spacing="md">
      {items.map((item) => (
        <Paper key={item.label} p="md" radius="md" withBorder>
          <Group justify="space-between" mb={4}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
              {item.label}
            </Text>
            <ThemeIcon variant="light" color={item.color} size="sm" radius="xl">
              {item.icon}
            </ThemeIcon>
          </Group>
          <Text size="xl" fw={700}>
            {item.value}
          </Text>
        </Paper>
      ))}
    </SimpleGrid>
  );
}
