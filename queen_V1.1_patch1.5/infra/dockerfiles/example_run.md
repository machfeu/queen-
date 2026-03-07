# Example Run — Walkthrough complet

## 1. Soumettre un objectif

Via le dashboard (http://localhost:8080 → Goals → Nouvel objectif) ou via curl :

```bash
curl -X POST http://localhost:8080/api/goals \
  -H "Content-Type: application/json" \
  -d @example_goal.json
```

Réponse :
```json
{"goal_id": "goal_a1b2c3d4", "status": "pending"}
```

## 2. Le pipeline se déclenche automatiquement

L'orchestrateur :
1. Passe le goal en statut `planning`
2. Appelle le LLM pour décomposer l'objectif en jobs
3. Crée un **run** et les **jobs** associés
4. Dispatche les jobs dans Redis

## 3. Observer dans le dashboard

- **Overview** : le run apparaît dans "Runs récents", les jobs dans "Jobs récents"
- **Runs** : cliquer sur le run → page RunDetail avec :
  - Timeline visuelle des étapes (research → codegen → test → eval → patch)
  - Score global avec barres par critère
  - Table des jobs avec logs expansibles

## 4. Les workers exécutent les jobs

Séquence typique :

| Step | Type     | Action                                              |
|------|----------|-----------------------------------------------------|
| 1    | research | Analyse le workspace existant, identifie les fichiers |
| 2    | codegen  | Génère le code de l'endpoint + test unitaire        |
| 3    | test     | Vérifie la syntaxe, lint, patterns dangereux        |
| 4    | eval     | Score la qualité du résultat                        |
| 5    | patch    | Collecte les fichiers générés pour le diff          |

## 5. Scoring et évaluation

L'évaluateur attribue un score entre 0 et 1 :
- **> 0.7** → verdict `approve` → le patch passe aux gates
- **0.3 - 0.7** → verdict `retry` → on peut relancer
- **< 0.3** → verdict `reject` → échec

## 6. Gates automatiques

Si le verdict est `approve`, les gates s'exécutent :
- **code_safety** : vérifie l'absence de patterns dangereux (eval, exec, subprocess...)
- **syntax_check** : compile les fichiers Python
- **path_validation** : vérifie que les fichiers sont dans /workspace

## 7. Voir le patch dans le dashboard

- **Patches** → le patch apparaît avec son statut (`gates_passed` ou `gates_failed`)
- Cliquer → **PatchDiffModal** s'ouvre avec :
  - Le diff coloré (vert = ajouts, rouge = suppressions)
  - Les résultats des gates (✓/✗ par gate)
  - Les boutons d'action

## 8. Approuver et appliquer

Si les gates sont passées :
1. Cliquer **Approuver** → statut passe à `approved`
2. Cliquer **Appliquer** → le patch est écrit dans `/workspace/goal_xxx/`
3. Le goal passe à `completed`

Si erreur après application :
- Cliquer **Rollback** → restaure depuis le backup automatique

## 9. Vérifier le résultat

```bash
# Lister les fichiers du workspace via l'API
curl http://localhost:8080/api/workspace?path=goal_a1b2c3d4

# Ou inspecter le volume Docker
docker compose exec dashboard ls /workspace/goal_a1b2c3d4/
```

## 10. Journal d'audit

Toutes les actions sont tracées :
```bash
curl http://localhost:8080/api/audit?limit=20
```

Chaque entrée contient : timestamp, action, entité, acteur, détails.
