# Refactoring Patterns

## Principes

- Refactorer en petits pas vérifiables
- Les tests doivent passer AVANT et APRÈS chaque étape
- Ne jamais refactorer et ajouter une feature en même temps

## Patterns courants

### Extract Function
Quand un bloc de code fait plus d'une chose, extraire en fonction nommée.
Signe : un commentaire qui explique ce que fait un bloc → c'est le nom de la fonction.

### Replace Temp with Query
Variable temporaire utilisée une seule fois → remplacer par un appel de méthode.

### Introduce Parameter Object
3+ paramètres liés → les grouper dans une dataclass.

### Replace Conditional with Polymorphism
Cascade de if/elif sur un type → utiliser un dict de handlers ou des classes.

### Simplify Conditional
Conditions complexes → extraire en fonctions booléennes nommées.

### Remove Dead Code
Code commenté, fonctions jamais appelées, imports inutilisés → supprimer.

## Checklist de refactoring

- [ ] Les tests passent avant de commencer
- [ ] Un seul refactoring à la fois
- [ ] Les tests passent après chaque changement
- [ ] Pas de changement de comportement (même entrées → mêmes sorties)
- [ ] Le code est plus court OU plus lisible (idéalement les deux)
- [ ] Commit après chaque refactoring réussi
