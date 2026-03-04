# Code Evaluation

Guide pour évaluer la qualité du code Python avec des exemples calibrés.

## Échelle de scores

- **0.9-1.0** : Excellent — code production-ready, bien testé, documenté
- **0.7-0.9** : Bon — fonctionne, quelques améliorations possibles
- **0.5-0.7** : Acceptable — fonctionne mais des problèmes notables
- **0.3-0.5** : Insuffisant — bugs ou problèmes sérieux
- **0.0-0.3** : Rejeté — ne fonctionne pas ou dangereux

## Exemples calibrés

### Exemple 1 : Score 0.9 (Excellent)

```python
def find_duplicates(items: list[str]) -> list[str]:
    """Retourne les éléments qui apparaissent plus d'une fois."""
    seen = set()
    duplicates = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)
```

Pourquoi 0.9 : complexité O(n), typé, documenté, edge cases gérés (liste vide → []), nommage clair, retour déterministe (sorted).

### Exemple 2 : Score 0.5 (Acceptable)

```python
def find_duplicates(items):
    result = []
    for i in range(len(items)):
        for j in range(i+1, len(items)):
            if items[i] == items[j] and items[i] not in result:
                result.append(items[i])
    return result
```

Pourquoi 0.5 : fonctionne mais O(n²), pas typé, pas documenté, `not in result` est O(n) à chaque itération.

### Exemple 3 : Score 0.2 (Rejeté)

```python
def find_duplicates(items):
    return list(eval(f"{{x for x in {items} if {items}.count(x) > 1}}"))
```

Pourquoi 0.2 : utilise eval() (faille de sécurité), O(n²) via count(), fragile (crash si items contient des quotes), illisible.

## Critères d'évaluation

### Correctness (40% du score)
- Le code fait-il ce qui est demandé ?
- Gère-t-il les edge cases (vide, None, très grand) ?
- Y a-t-il des bugs silencieux ?

### Security (25% du score)
- Utilise-t-il eval/exec/subprocess ?
- Valide-t-il les entrées ?
- Y a-t-il des path traversal possibles ?

### Maintainability (20% du score)
- Le code est-il lisible ?
- Les fonctions sont-elles courtes et focalisées ?
- Y a-t-il des type hints et docstrings ?

### Performance (15% du score)
- La complexité algorithmique est-elle raisonnable ?
- Y a-t-il des allocations inutiles ?
- Le code scale-t-il ?

## Verdicts

- **approve** : score >= 0.7 ET pas de critical_issues
- **retry** : score entre 0.5 et 0.7, ou critical_issues corrigeable
- **reject** : score < 0.5 OU faille de sécurité OU eval/exec utilisé
