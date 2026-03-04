# Notes Sécurité — Queen V1

## Menace principale

**Exécution de code arbitraire via le LLM.**
Le système demande à un LLM de générer du code, puis l'exécute (indirectement
via les workers). Un prompt injection ou un modèle malveillant pourrait générer
du code dangereux.

## Comment la V1 limite les risques

### 1. Isolation par conteneur
- Les workers tournent dans des containers dédiés, en **user non-root**
- Ils ne peuvent écrire que dans `/workspace` (volume partagé, pas l'hôte)
- Le réseau Docker est isolé (`queen_net`), pas d'accès Internet depuis les workers

### 2. Analyse statique avant exécution
- **Blocklist de patterns** : `eval()`, `exec()`, `os.system()`, `subprocess.Popen()`,
  `rm -rf`, `curl | bash`, netcat, reverse shells...
- **Blocklist de packages** : `paramiko`, `fabric`, `nmap`, `scapy`...
- **Validation des chemins** : tout fichier doit être dans `/workspace`, pas de `..`
- **Extensions autorisées** : whitelist stricte (`.py`, `.json`, `.md`, etc.)

### 3. Gates obligatoires avant intégration
- **syntax_check** : le code compile sans erreur
- **code_safety** : aucun pattern dangereux détecté
- **path_validation** : aucun fichier hors workspace
- Si une gate échoue → le patch est rejeté automatiquement

### 4. Approbation humaine
- Par défaut, `require_manual_approval = true`
- Un patch ne peut être appliqué que si un humain clique "Approuver" puis "Appliquer"
- Le journal d'audit trace qui a approuvé quoi et quand

### 5. Budgets et timeouts
- Chaque job a un timeout (300s par défaut, max 1800s)
- Taille de sortie limitée (10 MB par défaut)
- Nombre de jobs par run limité (20 max)
- Plus le risque est élevé, plus les budgets sont serrés

### 6. Backup et rollback
- Avant chaque application de patch, un backup est créé dans `/workspace/.queen_backups/`
- Le bouton "Rollback" restaure l'état précédent
- Traçabilité complète via le journal d'audit

### 7. Secrets
- Les clés API sont uniquement dans les variables d'environnement
- Jamais logées, jamais dans le code source
- Le fichier `.env` est dans `.gitignore`

## Ce que la V1 ne couvre PAS (axes V2)

| Risque résiduel | Mitigation future |
|---|---|
| Le LLM peut produire du code subtil qui passe la blocklist | Sandboxing renforcé (gVisor/Firecracker), analyse sémantique |
| Les workers partagent le volume /workspace | Volumes par job, nettoyage automatique |
| Pas de rate limiting sur l'API dashboard | Middleware rate limit + auth token |
| Pas de chiffrement de la DB SQLite | Chiffrement au repos (SQLCipher) |
| Pas d'audit sur les lectures (GET) | Logging exhaustif en V2 |
| Le modèle Ollama local n'est pas validé | Checksums de modèles, provenance vérifiée |

## Principes

- **Safe-by-default** : tout ce qui n'est pas explicitement autorisé est interdit
- **Defense in depth** : plusieurs couches (container, analyse statique, gates, approbation humaine)
- **Ne jamais prétendre "impossible à pirater"** : la V1 réduit la surface d'attaque, elle ne l'élimine pas
