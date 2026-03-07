# Testing Strategies

## Principes

- Chaque modification doit avoir au moins un test
- Les tests doivent être rapides (< 1s unitaire, < 10s intégration)
- Tester le comportement, pas l'implémentation

## Structure de test

```python
def test_nom_descriptif():
    # Arrange — préparer les données
    input_data = {"key": "value"}

    # Act — exécuter l'action
    result = function_under_test(input_data)

    # Assert — vérifier le résultat
    assert result.status == "ok"
```

## Types de tests par priorité

1. **Tests unitaires** : une fonction isolée, mocks pour les dépendances
2. **Tests de régression** : reproduire un bug avant de le fixer
3. **Tests d'intégration** : vérifier que les modules communiquent
4. **Tests de bordure** : entrées vides, None, très grandes, unicode

## Patterns utiles

- Fixtures pour les données de test réutilisables
- Parametrize pour tester plusieurs cas d'un coup
- Mocking avec `unittest.mock.patch` pour isoler les dépendances externes
- `tmp_path` (pytest) pour les tests de fichiers

## Checklist avant commit

- [ ] Tous les tests existants passent
- [ ] Nouveau code couvert par au moins un test
- [ ] Pas de `print()` ou `breakpoint()` oubliés
- [ ] Tests déterministes (pas de dépendance au temps ou à l'aléatoire)
