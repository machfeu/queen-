# Queen — Vision, portée et état du projet

## Ce qu’est Queen

Queen est un **système local d’orchestration et d’évolution logicielle** pensé comme une base de travail pour une IA outillée capable de :
- recevoir un objectif,
- le découper en actions,
- générer des jobs,
- évaluer des variantes,
- appliquer des patches,
- rollbacker si nécessaire,
- et améliorer progressivement son propre comportement dans un cadre contrôlé.

Le projet ne cherche pas à faire une "IA magique" ou une autonomie floue. Il cherche à construire, étape par étape, une **plateforme technique crédible** où l’auto-amélioration est :
- **traçable**, 
- **testable**,
- **réversible**,
- **pilotable depuis une interface**,
- et **suffisamment robuste** pour être utilisée localement sans bricolage permanent.

## Ce que Queen essaie de résoudre

Dans beaucoup de projets IA, le vrai problème n’est pas de générer du texte, mais de transformer une intention en exécution fiable :
- préparer l’environnement,
- gérer les fichiers,
- faire circuler les consignes,
- contraindre les modifications,
- scorer les variantes,
- promouvoir les bonnes,
- annuler les mauvaises,
- et donner à l’utilisateur un vrai contrôle.

Queen répond à ce besoin en combinant :
- une **stack Docker locale**,
- un **orchestrateur**,
- des **workers** spécialisés,
- une **mémoire SQLite**,
- un **dashboard web**,
- un **launcher Windows**,
- un **workspace exploitable depuis l’interface**,
- et un **moteur d’évolution** avec benchmark, promotion et rollback.

## Architecture fonctionnelle en une phrase

Queen est aujourd’hui une **colonie logicielle pilotée localement**, où un orchestrateur distribue du travail à des workers, où les fichiers vivent dans un workspace partagé, où les états sont stockés en base, et où les évolutions sont évaluées avant d’être éventuellement promues.

## Ce que le projet n’est pas encore

Il est important de rester honnête.

Queen n’est pas encore :
- une IA générale autonome,
- une plateforme multimodale mature,
- un système de sélection darwinienne entièrement robuste de bout en bout,
- une stack cloud industrielle multi-instance,
- ni un produit final figé.

Le projet est aujourd’hui une **base sérieuse en forte consolidation**, avec plusieurs briques déjà crédibles, mais aussi des zones encore en construction.

## Ce qui est déjà solide

À ce stade, le projet dispose déjà de bases réelles et utilisables :
- stack Docker fonctionnelle,
- dashboard exploitable,
- launcher Windows renforcé,
- auth plus propre,
- workspace pilotable depuis l’UI,
- promotion/rollback largement fiabilisés,
- benchmark statique + fonctionnel,
- mini-flux métier Queen benchmarké,
- bootstrap environnement Docker/Ollama,
- câblage `target_files` de l’UI jusqu’au moteur.

## Ce qui reste encore à fiabiliser

Les chantiers encore ouverts ne remettent pas la base à zéro, mais ils comptent pour la suite :
- enforcement dur de `target_files`,
- durcissement final de certains points Docker,
- validation frontend réelle systématique sur machine cible,
- healthchecks réellement exécutables dans toutes les images,
- progression vers des benchmarks métier encore plus complets,
- montée en puissance du produit sans perdre en lisibilité ni en contrôle.

## Pourquoi ce document existe

Ce document sert à garder une trace claire des **tenants et aboutissants** du projet :
- d’où Queen part,
- ce qui a été réellement implémenté,
- quels bugs ont été corrigés,
- quelles décisions ont été prises,
- ce qui est stable,
- et ce qui reste à construire.

Le but est d’éviter deux dérives classiques :
1. **sur-vendre** le projet comme s’il était déjà terminé,
2. **sous-estimer** le travail déjà accompli en repartant sans cesse de zéro.

La logique de ce suivi qualité est donc simple :
> documenter honnêtement l’évolution de Queen pour garder le cap technique, éviter les régressions, et rendre la suite du projet lisible.

---
# Queen — Suivi qualité complet des versions et des correctifs

## Objectif du document

Ce document sert de **journal technique de qualité** pour le dépôt GitHub de Queen.
Il récapitule, version par version, les **implémentations livrées**, les **bugs corrigés**, les **régressions évitées**, les **limites restantes**, ainsi que la **suite logique du projet**.

Le but n'est pas de faire du marketing. Le but est de garder une trace claire de :
- ce qui a réellement été ajouté,
- ce qui a réellement été corrigé,
- pourquoi ces corrections étaient nécessaires,
- et où en est réellement le projet.

---

# 1. Résumé exécutif

Queen a évolué d'une base encore fragile vers une **plateforme locale sérieuse**, avec :
- une stack Docker exploitable,
- un dashboard opérationnel,
- un launcher Windows plus robuste,
- un moteur d'évolution mieux encadré,
- une promotion/rollback bien plus fiable,
- un benchmark fonctionnel moins aveugle,
- une gestion du workspace intégrée à l'interface,
- une intégration Goal ↔ Workspace,
- et un bootstrap environnement (Docker/Ollama) beaucoup plus simple à utiliser.

### État actuel honnête

Queen n'est plus un prototype brut.
Mais Queen n'est pas encore une plateforme d'auto-amélioration totalement robuste et autonome.

### Formulation correcte

> Queen est aujourd'hui une **base stabilisée et exploitable**, avec un vrai noyau de mutation, de benchmark et d'orchestration. En revanche, le système reste encore en construction sur certains aspects stratégiques : enforcement dur de `target_files`, durcissement complet de la couche Docker, validation frontend réelle systématique, et montée en puissance des benchmarks métier.

---

# 2. Version de référence recommandée

## Base de travail recommandée actuelle

**Queen v1.8 stabilisée** composée de :
- stabilisation 1B,
- lot 3 UI/UX,
- benchmark v2.1,
- lot A atomicité `apply_patch`,
- lot B + B.1 isolation d'exécution des benchmarks utilisateur,
- lot C + C.1 mini-flux Queen via `actions.apply_patch()`,
- suppression de `fix_actions/`,
- Workspace + Workspace 1.1,
- Bootstrap lot 1 + lot 2,
- câblage `target_files` dans le pipeline.

---

# 3. Historique par version

## v1.1 final — Base historique

### Ce que cette version représentait
- base fonctionnelle initiale,
- architecture Docker déjà présente,
- séparation orchestrateur / workers / dashboard / Redis,
- première version sérieuse du noyau Queen.

### Limites majeures héritées
- sécurité incomplète,
- peu de garde-fous sur les chemins et les patchs,
- forte dépendance à des comportements implicites,
- faible observabilité,
- gestion encore brute du dashboard et des dépendances.

### Pourquoi cette base était insuffisante
Parce qu'elle posait les fondations, mais pas encore les garanties de robustesse nécessaires pour une mutation ou une évolution automatique crédible.

---

## v1.2 / patch 1.2 — enrichissements intermédiaires

### Apports principaux
- enrichissements de patterns,
- mise à jour de contenus et de textes,
- amélioration progressive de la structure du projet.

### Problème de fond
La base restait encore surtout orientée prototype. Beaucoup de mécanismes existaient, mais n'étaient pas encore durcis.

---

## v1.3 / patch 1.3 — amélioration continue

### Apports
- intégration d'améliorations supplémentaires,
- montée en cohérence du projet,
- enrichissement du comportement global.

### Limite
Les correctifs n'étaient pas encore centralisés dans une logique de qualité globale. On améliorait, mais sans encore verrouiller sérieusement les risques de corruption, de sécurité ou d'UX bancale.

---

## v1.4 — montée en ambition, mais base encore fragile

### Ce que v1.4 a tenté
- enrichir les comportements,
- étendre le périmètre,
- préparer une base plus vivante.

### Problèmes connus hérités ensuite
- parseur de diff `_parse_unified_diff()` encore fragile,
- logique patch/apply incomplète,
- plusieurs bugs hérités qui réapparaîtront dans les audits 1.5.

### Pourquoi c'était un problème
Parce que la complexité augmentait plus vite que la fiabilité.

---

## v1.5 — Version auditée en profondeur

v1.5 est la première version sur laquelle un vrai **travail de qualification qualité** a été mené de façon structurée.

### Bugs majeurs identifiés à cette étape
- lecture mémoire non atomique dans l'orchestrateur,
- parseur de diff encore cassant,
- thread zombie sur timeout worker,
- snapshot d'évolution vide si `EVOLUTION_SOURCE_ROOT` absent,
- consensus trop agressif,
- fallback fragile dans le worker eval,
- WebSocket créant sa propre connexion Redis,
- archive SQLite sans verrou,
- `dry_run` trompeur pour les smoke checks,
- politique `eval(` / `ast.literal_eval` mal gérée,
- `get_stats()` fragile,
- score de fitness mal borné,
- `subprocess.TimeoutExpired` non géré dans certains chemins,
- `startup` FastAPI déprécié,
- résolution de chemin `self_heal` encore risquée,
- `/api/settings` trop exposé,
- absence d'auth crédible sur l'API,
- validation de webhook faible,
- limites snapshot inexistantes,
- chemins workspace encore faibles.

### Pourquoi cette étape est importante
Parce que v1.5 a servi de **point de vérité** : elle a révélé précisément ce qui empêchait Queen de devenir une base sérieuse.

---

## v1.6 — Gros patch, mais régressions réelles

### Ce qui a été réellement amélioré
- whitelists SQL dans `memory.py`,
- timestamps timezone-aware sur une grande partie du code,
- verrou SQLite + UUID côté archive d'évolution,
- validation des webhooks,
- logs de lecture dans `mutator.py`,
- meilleure robustesse sur certaines routes API,
- migration partielle vers `lifespan`.

### Régressions / problèmes restants
- auth dashboard incohérente frontend/backend/WS,
- “fix” faux sur le thread zombie (`daemon=True`),
- durcissement Redis incomplet,
- `_wait_for_jobs()` encore pas totalement propre,
- `patcher.py` encore fragile,
- lots trop mélangés entre sécurité réelle et confort.

### Pourquoi v1.6 n'était pas la base finale
Parce qu'elle était meilleure que 1.5, mais pas suffisamment propre pour être retenue sans reprise.

---

## v1.6.1 — Première base sérieuse

### Ce qui a été corrigé
- auth unifiée backend / frontend / WebSocket,
- vrai kill de process côté worker timeout,
- parseur de diff amélioré pour les cas de suppression pure,
- `dry_run` mieux géré,
- contrôle de chemin renforcé via `realpath/commonpath`,
- Redis AUTH traité de manière plus propre,
- cohérence bien meilleure du dashboard.

### Pourquoi cette version compte
Parce que c'est la première version qui pouvait être considérée comme **base de travail sérieuse**.

### Limites restantes
- encore pas de benchmark métier complet,
- encore pas de workspace UX propre,
- encore pas de bootstrap environnement avancé.

---

## v1.7 — UI évolution + launcher desktop

### Implémentations apportées
- page dashboard **Evolution**,
- manager backend d'évolution pilotable,
- lancement/arrêt de l'évolution sans ligne de commande,
- progression et événements live,
- top sélection / archive des variantes,
- launcher desktop (`queen_launcher.py`, `.bat`, `.vbs`),
- édition simplifiée du `.env`,
- démarrage/arrêt/restart Docker depuis le launcher,
- ouverture simplifiée du dashboard.

### Pourquoi c'était utile
Parce que Queen cessait d'être un outil réservé au terminal pour devenir un vrai produit local pilotable.

### Limite honnête
La sélection “darwinienne” restait encore surtout un **MVP pilotable** : meilleure UX, mais pas encore assez de signal métier.

---

# 4. v1.8 — Phase de stabilisation majeure

v1.8 est la plus grosse phase de consolidation du projet.

---

## v1.8 — Lot 1 → 1.3 : promotion / rollback

### Lot 1 — première promotion/rollback
#### Implémentation
- ajout d'une promotion de variante depuis l'archive,
- ajout d'un rollback de promotion,
- statut de promotion exposé via API.

#### Problème
La première version était encore trop faible : cible arbitraire, promotion par overlay, rollback incomplet.

---

### Lot 1.1 — correction de sécurité et de cohérence
#### Corrections apportées
- suppression de `target_dir` arbitraire,
- remplacement plus fidèle des répertoires,
- blocage Zip Slip,
- multi-backups avec métadonnées,
- historique de backups.

#### Pourquoi c'était nécessaire
Pour éviter qu'une promotion n'écrive hors périmètre ou n'altère l'état de façon imprévisible.

---

### Lot 1.2 — rollback propre des nouveaux fichiers et des extractions partielles
#### Corrections
- rollback supprimant aussi les éléments créés par la promotion,
- restauration propre après extraction partielle.

#### Pourquoi
Parce qu'un rollback qui laisse des résidus n'est pas un rollback fiable.

---

### Lot 1.3 — durcissement final du périmètre
#### Corrections
- `commonpath` au lieu de `startswith`,
- validation stricte des entrées de backup/meta,
- meilleure défense contre les métadonnées forgées.

#### Résultat
**Promotion/rollback désormais acceptables comme brique sérieuse.**

---

## v1.8 — Lot 2 : benchmark v1 (statique)

### Implémentation
- premier benchmark injecté dans le fitness,
- séparation meilleure entre variantes propres et variantes grossières,
- pondération dédiée dans le score.

### Pourquoi
Avant ce lot, presque toutes les variantes qui compilaient avaient des scores trop proches.

### Limite
Ce benchmark était encore surtout **statique** : il voyait mieux la forme que le comportement réel.

---

## v1.8 — Lot 2.1a : correctifs mineurs

### Corrections
- commentaire nettoyé dans `models.py`,
- pagination workspace plafonnée,
- logs ajoutés pour échecs auth WebSocket.

### Pourquoi
Parce que même les petits angles morts accumulés dégradent la qualité de maintenance et de diagnostic.

---

## v1.8 — 1B : stabilisation structurante

### Corrections majeures
- **rate limiting API**,
- validation propre du chemin `/api/workspace` avec `commonpath`,
- rollback fichiers si la DB échoue après `apply_patch`,
- système de **migrations SQLite** minimal.

### Pourquoi c'était nécessaire
Parce que sans cela, Queen restait exposée à :
- abus de l'API,
- traversée de chemin,
- incohérence patch/DB,
- dérive de schéma SQLite.

### Limite restante
La transaction DB + filesystem n'était pas encore assez forte à ce stade.

---

## v1.8 — Lot 3 : UI promote/rollback + nettoyage d'exceptions silencieuses

### Implémentations
- boutons Promote / Rollback dans l'UI Evolution,
- statut de promotion visible,
- workflow sans `curl`,
- nettoyage partiel des `except: pass` les plus risqués.

### Pourquoi
Pour rendre l'outil utilisable sans shell et améliorer la lisibilité des échecs.

### Limite
Validation frontend réelle encore à vérifier localement au moment de la livraison.

---

## v1.8 — Benchmark v2

### Implémentation
- séparation **static_benchmarks** / **functional_benchmarks**,
- timeout par benchmark fonctionnel,
- scénarios fonctionnels réels (imports, policy, patcher).

### Pourquoi
Pour ne plus confondre “code propre” et “code qui marche”.

### Limite
Encore modulaire, pas encore flux métier continu.

---

## v1.8 — Benchmark v2.1

### Implémentations
- ajout de `memory_crud`,
- ajout de `migration_idempotence`,
- split explicite `static_score` / `functional_score` dans le fitness,
- veto fonctionnel si le comportement réel est mauvais.

### Pourquoi
Pour rendre le signal d'évolution plus crédible et davantage lié au fonctionnement réel.

### Résultat
Le système de benchmark devient enfin **moins aveugle**.

---

## v1.8 — Lot A : atomicité `apply_patch`

### Implémentation
- transaction DB groupée (`_execute_batch`, `apply_patch_atomic`),
- compensation ciblée par fichiers touchés,
- rollback des nouveaux fichiers créés par le patch,
- erreur explicite si le rollback échoue.

### Pourquoi c'était crucial
Parce que `apply_patch` était un point de rupture critique : fichiers modifiés, DB potentiellement incohérente, retour arrière incomplet.

### Résultat
Le chemin `apply_patch` devient **beaucoup plus fiable**.

---

## v1.8 — Lot B + B.1 : isolement des benchmarks utilisateur

### Lot B — première isolation
#### Implémentation
- découverte AST sans exécution module-level,
- exécution en subprocess,
- timeout,
- nettoyage partiel de l'environnement,
- crash benchmark isolé du process principal.

#### Pourquoi
Pour éviter qu'un benchmark utilisateur ne bloque ou ne fasse tomber Queen.

#### Limite
Ce n'était pas un vrai sandbox sécurité fort, seulement une isolation d'exécution légère.

---

### Lot B.1 — finitions critiques
#### Corrections
- fallback `stdout` non parseable → score `0.0` au lieu de `1.0`,
- `sys.executable` au lieu de `python3`,
- `os.pathsep` au lieu de `:`,
- `cwd` plus cohérent.

#### Pourquoi
Pour supprimer les faux positifs critiques et améliorer la portabilité.

---

## v1.8 — Lot C + C.1 : mini-flux Queen complet

### Lot C — mini-flux métier
#### Implémentation
- Goal,
- fallback plan,
- Run + Jobs,
- fallback eval,
- patch,
- apply,
- vérification,
- rollback.

#### Limite initiale
Le premier lot passait encore par `patcher.apply_patch()` au lieu du vrai chemin métier.

---

### Lot C.1 — correction du vrai point d'application
#### Correction
- mini-flux recâblé sur `actions.apply_patch()`.

#### Pourquoi
Pour que le benchmark teste enfin le **vrai chemin métier compensé**, et pas seulement les briques isolées.

### Résultat
Le mini-flux benchmark devient **vraiment représentatif du pipeline Queen** sans LLM ni Redis réels.

---

## v1.8 — Suppression de `fix_actions/`

### Constat
- aucun usage réel,
- zéro référence,
- code en retard sur de nombreux correctifs,
- duplication dangereuse.

### Décision
- suppression du dossier,
- suppression du reliquat ZIP orphelin.

### Pourquoi
Un code mort dupliqué et dangereux ne doit pas rester dans le dépôt.

---

## v1.8 — Workspace

### Implémentations
- `GET /api/workspace`,
- `POST /api/workspace/upload`,
- `POST /api/workspace/import-url`,
- `POST /api/workspace/mkdir`,
- `DELETE /api/workspace`,
- page frontend Workspace,
- navigation, upload, import, suppression, preview texte.

### Pourquoi
Parce que le volume Docker nommé `/workspace` était correct techniquement mais mauvais en UX sans interface.

### Limite initiale
- prévisualisation fichier non cliquable,
- protection SSRF insuffisante sur `import-url`.

---

## v1.8 — Workspace 1.1

### Corrections
- fichiers cliquables dans `Workspace.tsx`,
- preview réellement accessible,
- durcissement SSRF : blocage localhost, IP privées, métadonnées cloud, loopback, etc.

### Pourquoi
Pour faire de Workspace une vraie fonctionnalité produit, pas seulement une API technique.

---

## v1.8 — Goal ↔ Workspace (UI)

### Implémentation
- sélecteur de fichiers depuis Workspace dans la modal Goal,
- upload inline depuis la modal,
- `constraints.target_files` injecté au submit.

### Pourquoi
Parce qu'un goal devait pouvoir cibler des fichiers sans obliger l'utilisateur à taper le chemin à la main.

### Limite initiale
Le champ était transmis, mais pas encore réellement consommé par le pipeline.

---

## v1.8 — Câblage `target_files`

### Implémentations
- injection dans `planner.py`,
- injection dans `_fallback_plan`,
- transmission via l'orchestrateur dans le payload job,
- injection dans `prompt_builder.py` sous la forme d'une section **Fichiers cibles**.

### Pourquoi
Pour que l'information parte bien de l'UI et arrive jusqu'au moteur de génération.

### Limite honnête
C'est une **orientation forte**, pas encore une **contrainte dure** : le système sait maintenant quoi cibler, mais il ne rejette pas encore explicitement toute modification hors `target_files`.

---

## v1.8 — Bootstrap / Environment Manager — lot 1

### Implémentations
- module `env_check.py`,
- détection Docker installé / engine prêt,
- détection Ollama installé / API répondante,
- détection modèle configuré,
- boutons de lancement,
- état visuel dans le launcher.

### Pourquoi
Pour réduire drastiquement la friction au démarrage.

---

## v1.8 — Bootstrap / Environment Manager — lot 2

### Implémentations
- boutons **Installer Docker Desktop** / **Installer Ollama**,
- guidage contextuel,
- prise en compte de WSL,
- aide réaliste sans promettre une installation magique silencieuse.

### Pourquoi
Parce que le produit devait pouvoir guider l'utilisateur proprement quand l'environnement n'était pas encore prêt.

---

## v1.8 — Lot infra Docker (en cours de finalisation)

### Implémentations déjà apportées
- déduplication des variables d'environnement via anchors YAML,
- rotation des logs,
- documentation plus claire des ports localhost et du profil Ollama,
- healthchecks ajoutés.

### Limite détectée
Les healthchecks HTTP reposent encore sur `curl`, qui n'est pas garanti dans toutes les images. Un micro-fix reste nécessaire pour rendre ces checks réellement exécutables partout.

### Pourquoi ce lot compte
Parce qu'une stack qui tourne n'est pas forcément une stack bien industrialisée.

---

# 5. Bilan des bugs majeurs corrigés

## Corrigés
- thread zombie côté worker timeout,
- auth dashboard incohérente,
- WebSocket Redis singleton,
- archive SQLite sans lock,
- `dry_run` smoke trompeur,
- `get_stats()` fragile,
- `eval(` / `ast.literal_eval` trop grossiers,
- consensus trop agressif,
- double lecture mémoire non atomique,
- workspace path traversal,
- `_resolve_path` trop permissif,
- absence de rate limiting API,
- absence de migrations SQLite,
- rollback `apply_patch` insuffisant,
- promotion/rollback trop fragiles,
- benchmark trop aveugle,
- logs auth WebSocket manquants,
- `fix_actions/` dangereux,
- absence d'interface Workspace,
- absence d'intégration Goal ↔ Workspace,
- absence de bootstrap environnement sérieux.

## Corrigés partiellement / encore ouverts
- `_parse_unified_diff()` encore perfectible,
- enforcement dur de `target_files`,
- sandbox sécurité fort pour benchmarks utilisateur,
- validation frontend réelle systématique par build local,
- transaction parfaite DB + filesystem impossible au sens ACID global,
- healthchecks Docker à finaliser sur les images sans `curl`.

---

# 6. État qualité actuel

## Ce qui est maintenant solide
- stack Docker locale exploitable,
- auth et sécurité de base bien meilleures,
- promotion/rollback utilisables,
- launcher et bootstrap sérieux,
- workspace produit utilisable,
- benchmark fonctionnel crédible,
- moteur de patch bien plus robuste,
- pipeline `target_files` orienté jusqu'au prompt.

## Ce qui est encore en construction
- contrainte dure sur les fichiers autorisés,
- benchmark métier encore plus riche,
- durcissement infra Docker final,
- validation frontend visuelle/build systématique,
- installation encore plus fluide côté launcher.

## Ce qui n'est pas prioritaire maintenant
- multimodal,
- recherche internet avancée,
- GPU Ollama automatisé,
- refonte complète des limites CPU/RAM.

---

# 7. Suite logique du projet

## Priorité 1 — Finaliser le lot infra Docker
- corriger les healthchecks HTTP pour ne pas dépendre de `curl`,
- valider le compose final en conditions réelles.

## Priorité 2 — Enforcement dur de `target_files`
- refuser les patchs/fichiers modifiés hors liste quand `target_files` est défini,
- transformer l'orientation en garde-fou réel.

## Priorité 3 — Validation locale finale
- `npm install && npm run build`,
- tests manuels de dashboard,
- goal → benchmark → évolution → promote → rollback.

## Priorité 4 — Packaging / release
- README final,
- guide de démarrage Windows,
- note de version,
- archive stable finale.

---

# 8. Formulation recommandée pour GitHub

> Queen a connu une phase de stabilisation majeure entre les versions 1.5 et 1.8. Le projet dispose maintenant d'un noyau sérieux : bootstrap environnement, workspace intégré, benchmark statique + fonctionnel, promotion/rollback, launcher, dashboard et pipeline de patch plus robuste. Le projet n'est pas encore une plateforme d'auto-amélioration totalement verrouillée, mais il est désormais suffisamment stable et structuré pour une vraie phase de consolidation finale et de publication.

---

# 9. Conclusion

Le projet a cessé d'être une simple démonstration bricolée.
Il est devenu un **système local structuré**, avec de vraies briques produit.

La bonne lecture n'est pas :
- “tout est fini”

La bonne lecture est :
- “le socle est enfin crédible, et la suite peut maintenant se faire proprement.”

