# Python Optimization

## Principes

- Mesurer avant d'optimiser (cProfile, timeit)
- Optimiser les algorithmes avant le micro-tuning
- Préférer les built-ins Python (map, filter, list comprehensions)
- Utiliser des structures de données adaptées (set pour lookups, deque pour FIFO)

## Techniques courantes

### Boucles
- Remplacer les boucles for par des list comprehensions quand c'est lisible
- Utiliser `enumerate()` plutôt que `range(len())`
- Éviter les appels de méthode répétés dans les boucles (cacher la référence)

### I/O
- Lire les fichiers par blocs, pas ligne par ligne pour les gros fichiers
- Utiliser `json.dumps()` avec `default=str` pour la sérialisation rapide
- Préférer `pathlib` pour la manipulation de chemins

### Mémoire
- Utiliser des générateurs (`yield`) pour les gros datasets
- `__slots__` sur les dataclasses fréquemment instanciées
- Éviter les copies inutiles (attention à `list()`, `.copy()`)

### Concurrence
- `threading` pour l'I/O bound
- `multiprocessing` pour le CPU bound
- `asyncio` pour les appels réseau multiples

## Anti-patterns à éviter
- String concatenation dans une boucle (utiliser `"".join()`)
- `import` à l'intérieur d'une fonction appelée souvent
- `try/except` comme flow control normal
- Nested dict access sans `.get()` (risque KeyError + lenteur)
