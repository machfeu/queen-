# Debugging Techniques

## Méthodologie

1. **Reproduire** — écrire un test minimal qui reproduit le bug
2. **Isoler** — réduire au plus petit code qui échoue
3. **Comprendre** — lire la stack trace de bas en haut
4. **Corriger** — fix minimal, une seule chose à la fois
5. **Vérifier** — le test de régression passe, rien d'autre ne casse

## Lecture d'une stack trace Python

- La dernière ligne = l'erreur et son message
- Lire de bas en haut pour suivre la chaîne d'appels
- Chercher la première ligne qui est dans NOTRE code (pas la stdlib)
- L'erreur est souvent 1-2 frames au-dessus de l'exception

## Erreurs courantes

### AttributeError: 'NoneType'
- Une variable est None quand on ne s'y attend pas
- Vérifier la valeur de retour des fonctions (souvent un .get() manquant)

### KeyError
- Clé absente d'un dict
- Utiliser `.get(key, default)` au lieu de `dict[key]`

### ImportError / ModuleNotFoundError
- Module pas installé ou mauvais chemin
- Vérifier PYTHONPATH et les __init__.py

### TypeError: argument
- Mauvais type passé à une fonction
- Vérifier les signatures, surtout avec les Optional

## Outils

- `traceback.print_exc()` pour logger proprement
- `pdb.set_trace()` ou `breakpoint()` pour debug interactif
- `logging.debug()` plutôt que `print()` (on peut filtrer par niveau)
- `repr()` plutôt que `str()` pour voir les types exacts
