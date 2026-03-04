# Python Best Practices

## Style

- PEP 8 : 4 espaces, snake_case, 79 chars max (ou 120 si le projet le permet)
- Docstrings pour toute fonction publique
- Type hints sur les signatures de fonctions
- Noms descriptifs > commentaires

## Structure de code

- Un module = une responsabilité
- Fonctions courtes (< 30 lignes idéalement)
- Éviter les globals mutables
- Préférer la composition à l'héritage
- Dataclasses ou NamedTuple pour les données structurées

## Gestion d'erreurs

- Attraper des exceptions spécifiques, jamais `except Exception`
- Toujours logger avant de re-raise
- Utiliser des valeurs par défaut plutôt que des try/except pour les cas normaux
- Les fonctions retournent un type cohérent (pas parfois None, parfois une liste)

## Fichiers et I/O

- Toujours utiliser `with` pour les fichiers
- Encoder explicitement en UTF-8
- Valider les chemins (pas de path traversal)
- Limiter la taille des lectures (pas de `read()` sans limite sur un fichier inconnu)

## Sécurité

- Jamais `eval()`, `exec()`, ou `__import__()` sur des données utilisateur
- Pas de `subprocess.shell=True`
- Valider toutes les entrées externes
- Les secrets dans des variables d'environnement, jamais dans le code
