# Registre piighost catalog

Les motifs, groupes et configs officiels, un dossier par objet. Le format est
décrit dans [docs/hub/manifest.md](../docs/hub/manifest.md), la résolution et les
commits dans [docs/hub/resolution.md](../docs/hub/resolution.md).

## Ajouter un lot de motifs

Une recherche rend une liste de propositions, pas un fichier TOML. Le script
les valide toutes avant d'en écrire une seule, donc les défauts arrivent
ensemble plutôt qu'un par passage de vérificateur :

```bash
python3 scripts/new_patterns.py propositions.json --dry-run   # rapport seul
python3 scripts/new_patterns.py propositions.json             # écrit les manifestes
uv run python -m backend.hub check --allow-unrecorded
```

Il refuse un regex qui ne compile pas, une valeur d'exemple absente ou présente
deux fois, une valeur qui ne survit pas à la ponctuation adjacente, une
description en une seule langue, un tiret cadratin, un tag hors vocabulaire et
une recette de backtracking manquante.

## Ajouter ou modifier un motif

1. Créez ou éditez `patterns/piighost/<name>/pattern.toml`. Exemples synthétiques
   uniquement, tags pris dans `vocabulary.toml`.
2. `just hub-check` : structure, exemples, résilience, borne de backtracking,
   composition de tout ce qui utilise le motif.
3. `just hub-record` : enregistre la nouvelle tête comme commit immuable sous
   `commits/`. Committez le manifeste et l'instantané ensemble.
4. Pour déplacer un tag, éditez le `tags.toml` de l'objet avec le commit voulu.

Un commit enregistré ne se modifie ni ne se supprime. `hub check` le vérifie.
