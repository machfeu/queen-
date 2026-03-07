# Evolution (DGM-like) — MVP intégré à Queen

Objectif: intégrer **les idées utiles** de la Darwin Gödel Machine (DGM) dans Queen
sans reconstruire le projet.

Principe: Queen reste stable. L'évolution génère des **variantes candidates**
dans un dossier de travail, les **évalue**, puis les **archive** avec lignée.

## Ce que fait ce MVP

- Archive SQLite: `/data/queen_evolution.db`
- Patches archivés: `/data/evolution/patches/<variant_id>.diff`
- Snapshots archivés: `/data/evolution/snapshots/<variant_id>.zip`
- Sélection parent: score + pénalité du nombre d'enfants (diversité)
- Mutation: LLM propose 1–2 fichiers (contenu complet) sur une allowlist
- Évaluation: smoke tests (py_compile + imports clés)
- Fitness: priorité à la stabilité, bonus faible sur vitesse

## Ce que ce MVP NE fait pas (encore)

- Pas de benchmark long (type SWE-bench)
- Pas de "promotion" automatique dans le live
- Pas d'UI d'arbre (l'API existe, mais UI non ajoutée)

## Usage

Lancer une boucle d'évolution:

```bash
docker compose --profile evolver up --build
```

Configurer via `.env` (exemples):

```env
EVOLUTION_ITERS=8
EVOLUTION_MAX_FILES=2
EVOLUTION_TARGETS=queen_core/redis_bus.py
EVOLUTION_ALLOWLIST=queen_core/redis_bus.py,queen_core/orchestrator.py,workers/worker_unified.py
EVOLUTION_INSTRUCTION=Rends redis_bus plus résilient (retries/backoff) sans changer l'API publique.
```

Lister l'archive:

```bash
curl http://localhost:8080/api/evolution/variants
```

## Promotion manuelle (recommandé)

1) Ouvrir le patch `.diff` de la variante
2) L'appliquer sur ton repo
3) Relancer `docker compose up --build`
4) Valider avec tes smoke-tests / objectifs réels

## Sécurité

- La mutation est bornée par une allowlist de fichiers.
- Les patches passent par `policy.check_code_safety()`.
- Aucun `os.system` / `subprocess.Popen/call` n'est autorisé dans le code généré.
