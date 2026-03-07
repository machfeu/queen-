# 🐝 Queen V1 — Système d'auto-amélioration contrôlée

## Vue d'ensemble

Queen V1 est un noyau stable ("Queen Zero") qui s'améliore via une boucle
expérimentale contrôlée. Il ne mute jamais directement — toute modification
passe par un pipeline auditable : **Goal → Plan → Jobs → Score → Patch → Gates → Approbation humaine**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DOCKER COMPOSE                           │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  Redis    │◄──►│ Orchestrator │◄──►│  Worker 1 (& 2...)   │   │
│  │  (bus)    │    │  (cerveau)   │    │  research/codegen/   │   │
│  └────┬─────┘    └──────┬───────┘    │  test/eval/patch     │   │
│       │                 │            └──────────┬───────────┘   │
│       │           ┌─────┴──────┐               │               │
│       │           │  SQLite    │         ┌─────┴─────┐         │
│       │           │  (/data)   │         │ /workspace │         │
│       │           └────────────┘         │ (volumes)  │         │
│       │                                  └───────────┘         │
│  ┌────┴─────────────────────────┐                               │
│  │  Dashboard (FastAPI + React) │  ◄── http://localhost:8080    │
│  │  API REST + WebSocket        │                               │
│  └──────────────────────────────┘                               │
│                                                                 │
│  ┌──────────┐  (optionnel, --profile ollama)                    │
│  │  Ollama   │  ◄── LLM local, GPU passthrough                 │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Pipeline d'un objectif

```
  Objectif        Planning         Exécution        Scoring
  ┌──────┐      ┌─────────┐     ┌───────────┐    ┌──────────┐
  │ Goal │─────►│ Planner │────►│  Workers   │───►│Evaluator │
  └──────┘      │ (LLM)   │    │ via Redis  │    │  (LLM)   │
                └─────────┘    └───────────┘    └────┬─────┘
                                                      │
         Intégration         Validation          Patch │
        ┌───────────┐     ┌───────────┐     ┌────────┴──┐
        │  Apply    │◄────│   Gates   │◄────│  Patcher  │
        │(si human  │     │lint/test/ │     │(gen diff) │
        │ approve)  │     │ security  │     └───────────┘
        └───────────┘     └───────────┘
```

## Prérequis

- Linux avec Docker + Docker Compose v2
- (Optionnel) GPU NVIDIA + nvidia-container-toolkit pour Ollama
- 4 GB RAM minimum (8+ recommandé avec Ollama)

## Installation

```bash
# 1. Cloner / extraire le projet
cd queen_v1/

# 2. Copier et adapter les variables d'environnement
cp .env.example .env
nano .env  # Ajuster LLM_PROVIDER, modèle, etc.

# 3. Lancer (sans Ollama local)
docker compose up --build -d

# 3b. Lancer AVEC Ollama local + GPU
docker compose --profile ollama up --build -d

# 3c. Lancer avec 2 workers
docker compose --profile scale up --build -d

# 3d. (Optionnel) Lancer le mode "Evolution" (DGM-like MVP)
# Génère des variantes candidates et les archive dans /data/evolution
docker compose --profile evolver up --build

# 4. Vérifier que tout tourne
docker compose ps
docker compose logs -f orchestrator

# 5. Ouvrir le dashboard
xdg-open http://localhost:8080
```

## Télécharger un modèle Ollama (si profil ollama activé)

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

## Usage

## Evolution (DGM-like MVP)

Queen peut générer des **variantes candidates** (sans toucher au live) et les archiver
avec lignée parent → enfant (inspiré Darwin Gödel Machine).

Activation:

```bash
docker compose --profile evolver up --build
```

Artefacts:
- Patches archivés: `/data/evolution/patches/<variant_id>.diff`
- Snapshots archivés: `/data/evolution/snapshots/<variant_id>.zip`

API (read-only):
- `GET /api/evolution/variants`
- `GET /api/evolution/variants/{variant_id}`
- `GET /api/evolution/lineage/{variant_id}`

Promotion (manuel): appliquer le patch `.diff` sur ton repo/working tree.

### Via le Dashboard (recommandé)

1. Ouvrir http://localhost:8080
2. **Goals** → "Nouvel objectif" → remplir le formulaire → "Créer et lancer"
3. **Overview** → observer les runs et jobs en temps réel
4. **Runs** → cliquer sur un run → voir la timeline et les résultats
5. **Patches** → voir le diff → Approuver → Appliquer

### Via l'API (curl)

```bash
# Créer un objectif
curl -X POST http://localhost:8080/api/goals \
  -H "Content-Type: application/json" \
  -d @example_goal.json

# Lister les runs
curl http://localhost:8080/api/runs

# Voir la timeline d'un run
curl http://localhost:8080/api/runs/run_XXXX/timeline

# Approuver un patch
curl -X POST http://localhost:8080/api/patches/patch_XXXX/approve \
  -H "Content-Type: application/json" \
  -d '{"actor": "admin"}'

# Appliquer un patch approuvé
curl -X POST http://localhost:8080/api/patches/patch_XXXX/apply \
  -H "Content-Type: application/json" \
  -d '{"actor": "admin"}'

# Vérifier la santé
curl http://localhost:8080/api/health

# Métriques système
curl http://localhost:8080/api/metrics
```

### Swagger / OpenAPI

Documentation interactive : http://localhost:8080/docs

## Debug

```bash
# Logs de tous les services
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f orchestrator
docker compose logs -f worker-1
docker compose logs -f dashboard

# Shell dans un container
docker compose exec orchestrator bash
docker compose exec worker-1 bash

# Inspecter la DB
docker compose exec dashboard python -c "
import sqlite3, json
conn = sqlite3.connect('/data/queen.db')
conn.row_factory = sqlite3.Row
for r in conn.execute('SELECT id, title, status FROM goals'):
    print(dict(r))
"

# Inspecter le workspace
docker compose exec dashboard ls -la /workspace/

# Redis CLI
docker compose exec redis redis-cli
> LLEN queen:jobs
> LLEN queen:results
> LRANGE queen:log_history 0 5
```

## Arrêt et nettoyage

```bash
# Arrêter
docker compose down

# Arrêter + supprimer les volumes (ATTENTION: perd les données)
docker compose down -v

# Rebuild complet
docker compose build --no-cache
docker compose up -d
```

## Arborescence

```
queen_v1/
├── docker-compose.yml          # Stack complète
├── .env.example                # Template variables d'env
├── .gitignore
├── README.md                   # Ce fichier
├── SECURITY.md                 # Notes sécurité
├── example_goal.json           # Objectif exemple
├── example_run.md              # Walkthrough complet
│
├── queen_core/                 # Noyau stable (Queen Zero)
│   ├── __init__.py
│   ├── models.py               # Modèles + schéma SQLite
│   ├── memory.py               # Couche persistence
│   ├── orchestrator.py         # Cerveau principal
│   ├── planner.py              # Décomposition d'objectifs
│   ├── evaluator.py            # Scoring des résultats
│   ├── patcher.py              # Génération/application de diffs
│   ├── policy.py               # Règles sécurité + budgets
│   ├── llm_client.py           # Abstraction Ollama/OpenAI
│   ├── redis_bus.py            # Communication inter-services
│   └── requirements.txt
│
├── workers/                    # Workers sandboxés
│   ├── __init__.py
│   ├── worker_base.py          # Base avec timeout + Redis
│   └── worker_unified.py       # Handlers: research/codegen/test/eval/patch
│
├── dashboard/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── api.py              # FastAPI (23 endpoints + WebSocket)
│   │   ├── main.py             # Entry point uvicorn :8080
│   │   └── requirements.txt
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── index.html
│       └── src/
│           ├── main.tsx / App.tsx
│           ├── api/ (types, client, hooks)
│           ├── ws/ (useEvents)
│           ├── layout/ (Shell)
│           ├── pages/ (Overview, Goals, Runs, RunDetail, Patches, Settings)
│           └── components/ (StatCards, GoalCreateModal, Timeline,
│                            JobTable, PatchDiffModal, LogPanel)
│
└── infra/
    └── dockerfiles/
        ├── Dockerfile.orchestrator
        ├── Dockerfile.worker
        └── Dockerfile.dashboard
```

## Checklist de validation

- [ ] `docker compose up --build` démarre sans erreur
- [ ] `curl http://localhost:8080/api/health` retourne `{"status": "ok", ...}`
- [ ] Le dashboard s'affiche sur http://localhost:8080
- [ ] Créer un goal via le dashboard fonctionne
- [ ] Les runs et jobs apparaissent dans la timeline
- [ ] Les logs défilent en temps réel (WebSocket ou polling)
- [ ] Un patch est généré avec un diff visible
- [ ] Les gates s'exécutent (syntax + safety + path)
- [ ] Approve → Apply fonctionne
- [ ] Rollback restaure l'état précédent
- [ ] Le journal d'audit trace toutes les actions
- [ ] `docker compose down` arrête proprement
