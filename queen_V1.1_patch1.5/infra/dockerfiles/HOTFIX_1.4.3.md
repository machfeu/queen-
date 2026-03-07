# Hotfix 1.4.3 (post-revues IA) — Correctifs appliqués

Ce hotfix corrige des problèmes **fonctionnels** identifiés dans la v1.4, en restant minimal et compatible.

## Correctifs inclus

### 1) Self-heal: crash `run_id` non défini (CRITIQUE)
- `queen_core/self_heal.py`
- `_ask_llm_for_fix()` accepte désormais `run_id` et l'appel le fournit.
- Objectif: supprimer le `NameError` lors d'une tentative de self-heal.

### 2) Notifications: Telegram utilisable + retry
- `queen_core/notifier.py`
- Ajout `chat_id` via `NOTIFY_TELEGRAM_CHAT_ID` (ou `TELEGRAM_CHAT_ID`)
- Skip + warning si format `telegram` sans `chat_id`
- Retry simple (3 tentatives) pour 429/5xx et erreurs réseau
- Timestamp générique en UTC timezone-aware

### 3) Redis: éviter une connexion par appel
- `queen_core/redis_bus.py`
- ConnectionPool singleton + client singleton
- `get_recent_logs()` tolérant aux entrées JSON corrompues

### 4) Orchestrator: double-consommation des résultats (MAJEUR)
- `queen_core/orchestrator.py`
- `run_forever()` ne consomme plus `redis_bus.pop_result()` (les résultats sont consommés par `_wait_for_jobs(run_id)`).
- Empêche des runs en timeout avec résultats perdus.

### 5) Patcher: diff partiel ⇒ overwrite incomplet (MAJEUR)
- `queen_core/patcher.py`
- `generate_diff()` génère des hunks avec contexte **plein fichier** (`n=max(len(...))`) afin que `_parse_unified_diff()` puisse reconstruire un fichier complet.
- `generate_patch_from_artifacts()` ignore `artifacts` marqués `rejected` et normalise les chemins (strip slash)

### 6) Worker: normalisation chemin + anti-escape workspace
- `workers/worker_unified.py`
- Normalise `path` (slashes) + refuse si le chemin sort du workspace.
- Les artefacts `rejected` restent visibles côté résultat mais ne partent plus au patch (filtrés côté patcher).

### 7) Dashboard: CORS configurable
- `dashboard/backend/api.py`
- `CORS_ALLOW_ORIGINS` (liste séparée par virgules) + `CORS_ALLOW_CREDENTIALS`

### 8) SQLite: robustesse concurrence
- `queen_core/models.py`
- PRAGMA WAL + busy_timeout + foreign_keys + synchronous NORMAL

## Variables .env ajoutées (optionnelles)
- `NOTIFY_TELEGRAM_CHAT_ID`
- `CORS_ALLOW_ORIGINS`
- `CORS_ALLOW_CREDENTIALS`

