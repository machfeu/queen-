# Queen v1.4 — Dossier Qualité & Patchlog (v1.1 → v1.4)

Ce document est conçu pour être placé **à la racine** de Queen v1.4 afin de :
- comprendre rapidement **ce que fait le programme**,
- garder une trace claire des **patchs successifs (1.2 → 1.4)**,
- appliquer une routine de **suivi qualité** (tests, critères de validation, traçabilité).

---

## 1) Objectif du programme

**Queen** est un orchestrateur d’agents (“fourmis / workers”) exécutés en conteneurs Docker, qui :
1. reçoit un objectif (via dashboard),
2. le transforme en jobs (research / codegen / test / eval / patch),
3. pousse ces jobs dans une file Redis,
4. collecte les résultats,
5. applique (ou propose) des patches de code,
6. expose l’état et les métriques via un dashboard (API + UI).

**Philosophie** : la Queen reste le cerveau de coordination. Les workers exécutent et produisent des sorties reproductibles (logs, artefacts, patches).

---

## 2) Architecture (vue rapide)

### Services Docker (compose)
- **orchestrator** : boucle principale de la Queen (planification, dispatch, suivi run, notifications)
- **workers** : un ou plusieurs workers (types: research/codegen/test/eval/patch)
- **redis** : bus de jobs / événements (queues)
- **dashboard backend** : API HTTP (expose outils, rôles, skills, budget, notifications…)
- **dashboard frontend** : UI (création d’objectif, suivi run, visualisation)

### Flux de traitement (simplifié)
1. UI → backend : création d’objectif (avec rôle + contraintes)
2. Orchestrator : transforme en plan + jobs
3. Redis : file `queen:jobs`
4. Workers : consomment, exécutent, rendent compte
5. Orchestrator : agrège résultats, déclenche eval/patch/self-heal, notifie

---

## 3) Dossiers clés (repères)

- `queen_core/`
  - orchestrator, planner, evaluator, consensus, notifier, self_heal
  - registres `tool_registry.py`, `role_registry.py`, `skill_registry.py`
- `workers/`
  - worker_unified.py : worker multi-types, injection role/skills, règles d’exécution
- `dashboard/`
  - `backend/` : API (FastAPI/Flask selon stack), routes tools/roles/skills/budget/notifier
  - `frontend/` : UI
- `tools/` (patch 1.2)
  - outils déclaratifs (YAML)
- `roles/` (patch 1.2)
  - rôles prêts à l’emploi (YAML)
- `skills/` (patch 1.2)
  - “compétences” / conventions (YAML + SKILL.md)

---

## 4) Démarrage (quickstart)

### Build + run
```bash
docker compose up --build
```

### Smoke checks API
```bash
curl http://localhost:8080/api/tools
curl http://localhost:8080/api/roles
curl http://localhost:8080/api/skills
curl http://localhost:8080/api/budget
curl http://localhost:8080/api/notifications/status
```

### Vérifier la file Redis (jobs)
```bash
docker exec -it <stack>-redis-1 redis-cli LLEN queen:jobs
```

---

## 5) Patchlog (historique de ce qui a été ajouté)

> Référence: base **v1.1** puis application patchs **1.2**, **1.3**, **1.4**.

### 5.1 Patch 1.2 — Patterns (tools/roles/skills)
**Objectif** : rendre Queen configurable sans toucher au code, avec des briques déclaratives.

Ajouts principaux :
- Ajout des dossiers :
  - `tools/` : outils en YAML
  - `roles/` : rôles en YAML (ex: “researcher”, “codegen”, etc.)
  - `skills/` : compétences en YAML + `SKILL.md`
- Ajout des registres :
  - `queen_core/tool_registry.py`
  - `queen_core/role_registry.py`
  - `queen_core/skill_registry.py`
- Ajout de **PyYAML** aux requirements (core + backend)
- Mise à jour `docker-compose.yml` pour monter `tools/roles/skills` (read-only recommandé)
- Dashboard backend :
  - endpoints `GET /api/tools`, `GET /api/roles`, `GET /api/skills` (+ reload si implémenté)
- Planner / Orchestrator / Worker :
  - support de `constraints.role`
  - injection du rôle + skills dans les prompts système
  - règles runtime (file_write/python_exec/syntax_check) pour fiabiliser

Résultat attendu :
- création d’un objectif avec un **rôle** depuis l’UI
- la Queen alimente les workers avec un prompt enrichi, cohérent et traçable

---

### 5.2 Patch 1.3 — Budget + Context chaining + Prompt builder
**Objectif** : éviter les runs qui partent à l’infini, et améliorer la cohérence entre jobs.

Ajouts principaux :
- **Budget tracker** :
  - suivi (tokens/temps/coût/appels) + seuils + arrêt si dépassement
- **Chaînage de contexte** :
  - injection `previous_context` pour les jobs d’un même run
- **Prompt builder spécialisé** :
  - prompts adaptés selon type de job (research/codegen/test/eval/patch)
  - continue d’injecter rôle + skills (compat patch 1.2)
- Dashboard backend :
  - endpoint `GET /api/budget`

Résultat attendu :
- un run affiche ses budgets + alertes
- les jobs successifs “se comprennent” mieux grâce au contexte chainé

---

### 5.3 Patch 1.4 — Consensus + Self-heal + Webhooks
**Objectif** : fiabiliser l’évaluation, réparer automatiquement, notifier proprement.

Ajouts principaux :
1) **Consensus multi-évaluateurs**
   - `queen_core/consensus.py`
   - utilisé par le job `eval` + l’évaluateur global `queen_core/evaluator.py`
   - calibrage via un skill type `code-evaluation` (si présent)

2) **Self-heal automatique**
   - `queen_core/self_heal.py`
   - déclenché si un job `test` échoue
   - max 2 tentatives (évite boucles)

3) **Notifications Webhooks**
   - `queen_core/notifier.py`
   - orchestrator notifie : start/end, patch_ready, budget warn/exceeded, approve/apply/reject
   - Dashboard backend : `dashboard/backend/notifier_routes.py`
   - endpoints (exemples) :
     - `GET  /api/notifications/status`
     - `POST /api/notifications/webhook`
     - `POST /api/notifications/test`
     - `POST /api/notifications/enable?enabled=true`

Variables `.env` (selon implémentation) :
- `NOTIFY_WEBHOOK_URL`
- `NOTIFY_WEBHOOK_FORMAT` (slack|discord|telegram|generic)
- `NOTIFY_WEBHOOK_EVENTS` (optionnel)
- `NOTIFY_WEBHOOK_URL_2` (optionnel)

Résultat attendu :
- si tests cassent → tentative de réparation automatique
- évaluations plus robustes (moins “au doigt mouillé”)
- possibilité d’alerter dans un canal (Slack/Discord/Telegram/etc.)

---

## 6) Règles de suivi qualité (à appliquer à chaque run)

### 6.1 Critères “GO / NO-GO”
Un patch est **GO** si :
- les tests passent (ou absence de tests explicitement documentée),
- l’évaluateur retourne “approve” via consensus,
- pas de dépassement budget,
- logs exploitables (pas d’erreurs silencieuses).

Un patch est **NO-GO** si :
- échec tests après self-heal,
- consensus négatif,
- dépassement budget,
- patch non reproductible (manque de commandes/étapes).

### 6.2 Checklists
**Avant run**
- [ ] `docker compose up --build` OK
- [ ] API répond (`/api/tools`, `/api/roles`, `/api/skills`, `/api/budget`)
- [ ] `.env` renseigné si webhooks

**Pendant run**
- [ ] file Redis non bloquée (`LLEN queen:jobs` varie)
- [ ] logs orchestrator propres (pas d’exception loop)
- [ ] budget sous contrôle

**Après run**
- [ ] tests OK (ou rapport clair)
- [ ] eval OK (consensus)
- [ ] patch appliqué et versionné
- [ ] notification envoyée (si activée)

---

## 7) Traçabilité recommandée (pragmatique)

### 7.1 Naming
- Tag run : `RUN_YYYYMMDD_HHMM_<objectif_court>`
- Patch : `PATCH_YYYYMMDD_<sujet>`

### 7.2 Fichiers log
Garder :
- logs orchestrator
- logs workers
- patch diff (ou archive patch)
- état budget en fin de run

### 7.3 Exemple de bloc “rapport de run” (à copier)
```text
RUN_ID:
OBJECTIF:
ROLE:
BUDGET_MAX:
RESULTAT:
- Tests:
- Eval consensus:
- Patch:
- Notifications:
ARTEFACTS:
- zip/diff:
- logs:
NOTES:
- known issues:
```

---

## 8) Dépannage (symptômes fréquents)

- **LLEN=0 tout le temps** : orchestrator ne pousse pas de jobs → vérifier logs orchestrator + config run.
- **Workers up mais rien ne consomme** : mismatch queue name / type job / worker types.
- **/api/tools vide** : montages volumes `tools/roles/skills` absents ou YAML invalides → valider syntaxe.
- **Budget dépasse immédiatement** : seuil trop bas ou mauvaise calibration (désactiver temporairement pour debug).
- **Self-heal en boucle** : max tentatives mal configuré → imposer un “hard stop”.

---

## 9) Ce que Queen v1.4 n’est PAS (limites assumées)
- Ce n’est pas une “IA magique” qui garantit des patches corrects sans tests.
- Sans tests de projet, self-heal/eval restent limités.
- La qualité dépend fortement de :
  - la clarté des rôles,
  - la pertinence des skills,
  - les garde-fous (budget, consensus, règles worker).

---

## 10) Rappel opérationnel (ce qu’il faut faire pour rester propre)
- versionner chaque patch
- ne jamais merger “au feeling”
- faire passer les tests avant “approve”
- garder un patchlog clair (ce fichier)

---

Fin du document.
