/**
 * GoalCreateModal.tsx — Modal de création d'objectif.
 * Champs: titre, description, risque, timeout, critères de succès.
 */

import { useState } from "react";
import {
  Modal, TextInput, Textarea, Select, NumberInput, Button,
  Stack, Group, Text, Switch,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useCreateGoal } from "../api/hooks";

interface Props {
  opened: boolean;
  onClose: () => void;
}

export default function GoalCreateModal({ opened, onClose }: Props) {
  const createMut = useCreateGoal();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [riskLevel, setRiskLevel] = useState<string>("medium");
  const [timeout, setTimeout] = useState<number>(300);
  const [successCriteria, setSuccessCriteria] = useState("");
  const [manualApproval, setManualApproval] = useState(true);

  const reset = () => {
    setTitle("");
    setDescription("");
    setRiskLevel("medium");
    setTimeout(300);
    setSuccessCriteria("");
    setManualApproval(true);
  };

  const handleSubmit = () => {
    if (!title.trim()) {
      notifications.show({ title: "Erreur", message: "Le titre est requis", color: "red" });
      return;
    }

    createMut.mutate(
      {
        title: title.trim(),
        description: description.trim(),
        constraints: {
          risk_level: riskLevel,
          timeout,
          success_criteria: successCriteria.trim(),
          require_manual_approval: manualApproval,
        },
      },
      {
        onSuccess: (data) => {
          notifications.show({
            title: "Objectif créé",
            message: `${data.goal_id} — pipeline démarré`,
            color: "green",
          });
          reset();
          onClose();
        },
        onError: (e) => {
          notifications.show({ title: "Erreur", message: e.message, color: "red" });
        },
      }
    );
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Nouvel objectif"
      size="lg"
      centered
    >
      <Stack gap="sm">
        <TextInput
          label="Titre"
          placeholder="Ex: Optimiser le module de scoring"
          value={title}
          onChange={(e) => setTitle(e.currentTarget.value)}
          required
        />

        <Textarea
          label="Description"
          placeholder="Décrivez l'objectif en détail..."
          rows={4}
          value={description}
          onChange={(e) => setDescription(e.currentTarget.value)}
        />

        <Group grow>
          <Select
            label="Niveau de risque"
            data={[
              { value: "low", label: "🟢 Low — budget large" },
              { value: "medium", label: "🟡 Medium — défaut" },
              { value: "high", label: "🟠 High — budget restreint" },
              { value: "critical", label: "🔴 Critical — très limité" },
            ]}
            value={riskLevel}
            onChange={(v) => v && setRiskLevel(v)}
          />

          <NumberInput
            label="Timeout par job (s)"
            min={30}
            max={1800}
            step={30}
            value={timeout}
            onChange={(v) => typeof v === "number" && setTimeout(v)}
          />
        </Group>

        <Textarea
          label="Critères de succès"
          placeholder="Comment savoir que l'objectif est atteint ?"
          rows={2}
          value={successCriteria}
          onChange={(e) => setSuccessCriteria(e.currentTarget.value)}
        />

        <Switch
          label="Approbation manuelle requise avant application du patch"
          checked={manualApproval}
          onChange={(e) => setManualApproval(e.currentTarget.checked)}
        />

        <Text size="xs" c="dimmed">
          Le pipeline sera lancé automatiquement : planning → jobs → scoring → patch → gates.
        </Text>

        <Group justify="flex-end" mt="sm">
          <Button variant="subtle" onClick={onClose}>
            Annuler
          </Button>
          <Button onClick={handleSubmit} loading={createMut.isPending}>
            Créer et lancer
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
