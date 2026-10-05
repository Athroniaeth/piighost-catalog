# API HTTP du catalogue

*[English version](en/api.md).*

Lecture seule, publique, sous `/api/v1`. C'est ce que la bibliothèque piighost
et le site consomment. Les routes ne portent pas la clé d'API du template :
elles ne servent que ce que le registre publie, et un tiers doit pouvoir résoudre
une référence depuis son propre déploiement. Le quota par client et la limite de
taille de corps s'appliquent comme au reste de l'API. Le contrat exact est
`openapi.json` à la racine, régénéré par `just types`.

| Route | Renvoie |
|---|---|
| `GET /api/v1/vocabulary` | le vocabulaire des tags, avec `kind` et libellés |
| `GET /api/v1/refs?kind=&tag=` | la liste des objets : clé, type, description, tags, commit `latest`, pointeurs |
| `GET /api/v1/refs/{ns}/{name}` | un objet et la liste de ses commits |
| `GET /api/v1/refs/{ns}/{name}/{selector}` | un commit : digest, date, contenu figé |
| `GET /api/v1/refs/{ns}/{name}/{selector}/resolved` | la résolution : labels et provenance pour un motif ou un groupe, détecteurs et étages pour une config, et le pipeline rendu |
| `GET /api/v1/refs/{ns}/{name}/{selector}/pipeline.toml?memory=&keep_refs=` | le pipeline piighost en TOML, `application/toml` |
| `GET /api/v1/refs/{ns}/{name}/{selector}/snippets` | des extraits prêts à coller, un par cible |
| `GET /api/v1/search?q=&kind=&tag=&label=&sort=` | la recherche et les compteurs de facettes du résultat ; `sort` vaut `relevance`, `updated`, `used`, `labels` ou `name` |
| `GET /api/v1/stats?days=` | l'usage du registre sur une fenêtre, agrégé depuis des compteurs |
| `GET /api/v1/labels` | tous les labels que le registre peut émettre |
| `GET /api/v1/samples` | les textes annotés, avec leurs annotations |
| `GET /api/v1/diff/{ns}/{name}?before=&after=` | ce que deux commits détectent différemment. Pas d'écran sur le site, ni de commande dans la bibliothèque |
| `GET /api/v1/badge/{ns}/{name}?tag=` | un endpoint shields.io, pour afficher un commit dans un README. Pas d'écran non plus, par construction |

`{selector}` est un tag, `latest` compris, ou un commit de huit caractères
hexadécimaux. Les tags d'une recherche se combinent en ET : cocher deux facettes
restreint, ce qui est ce que les compteurs annoncent. Chaque résultat porte la
description bilingue, la date du dernier commit enregistré et le nombre de
commits, ce qu'une ligne du catalogue affiche.

## Routes interactives

Elles prennent un corps JSON et renvoient 200 : rien n'est créé, rien n'est
stocké. Le texte d'un appel n'est ni journalisé ni conservé, puisque c'est
précisément la donnée que le pipeline sert à cacher.

| Route | Corps | Rôle |
|---|---|---|
| `POST /api/v1/playground` | `{ref, text}` | lance un objet du registre sur un texte |
| `POST /api/v1/playground/candidate` | `{regex, text, label}` | essaie un regex qui n'est pas encore dans le registre |
| `POST /api/v1/playground/chat` | `{ref, messages}` | rejoue une conversation avec un assistant scripté |
| `POST /api/v1/compare` | `{refs, text}` | lance deux à quatre objets sur un texte et dit où ils divergent |
| `POST /api/v1/submissions/check` | `{kind, namespace, name, manifest}` | valide un manifeste et renvoie une pull request prête |

Deux chemins d'exécution, parce que le risque n'est pas le même. Un motif du
registre a passé la borne de backtracking, donc il tourne dans le processus, sur
un texte plafonné à 20 000 caractères. Un regex tapé par un visiteur n'a rien
passé, donc il tourne dans un sous-processus tué au bout de deux secondes : cela
coûte un démarrage de processus et ne peut pas bloquer le serveur.

Le chat est sans état : le client renvoie toute la conversation à chaque appel,
donc deux workers répondent pareil et rien n'a besoin d'être stocké entre deux
requêtes. La réponse de l'assistant est scriptée, ce qui rend la démo gratuite et
reproductible ; elle démontre l'aller-retour, la restauration et un jeton par
valeur, qu'un vrai modèle ne prouverait pas mieux.

## Cache

Chaque réponse sélectionnée porte `ETag: "<digest complet>"`. Un sélecteur qui est
un commit renvoie `Cache-Control: public, max-age=31536000, immutable`, car ce
contenu ne changera jamais. Un tag renvoie `Cache-Control: public, no-cache` : le
client peut garder la réponse mais doit la revalider, le tag ayant pu bouger.

## Erreurs

Corps `application/problem+json`.

| Code | Quand |
|---|---|
| 400 | un espace de noms, un nom ou un sélecteur ne suit pas la grammaire |
| 404 | objet, tag ou commit inconnu |
| 422 | la résolution échoue sur un commit servi, une collision de labels par exemple, ou un regex candidat qui ne compile pas ou qui dépasse son délai |

## Exemples

```bash
curl -s http://127.0.0.1:5173/api/v1/refs?kind=group | jq '.items[].key'
curl -s http://127.0.0.1:5173/api/v1/refs/piighost/fr/latest/resolved | jq '.labels[] | {label, pattern}'
curl -s "http://127.0.0.1:5173/api/v1/refs/piighost/fr-default/latest/pipeline.toml?memory=redis" -o pipeline.toml
```

## Ce qui est compté

Le catalogue compte son usage, et la forme du stockage est le garde-fou plutôt que la
discipline. Ce n'est pas un journal de requêtes auquel on aurait retiré des
colonnes : c'est une table de compteurs, agrégée à l'écriture.

- La résolution la plus fine est l'heure. Aucune ligne ne correspond à une
  requête, donc il n'y a rien à corréler.
- Les colonnes sont la forme de l'appel : son genre, l'objet du registre nommé,
  si la référence était épinglée, si l'appelant était un navigateur ou la
  bibliothèque, et le statut. Jamais d'adresse, jamais la chaîne user-agent,
  jamais de session, jamais de corps.
- L'écriture est un `INSERT ... ON CONFLICT DO UPDATE SET count = count + 1`,
  donc deux appels identiques dans la même heure sont indistinguables par
  construction.

Le comptage se fait en mémoire et se vide sur minuterie, donc le chemin chaud
est une incrémentation de dictionnaire : un disque lent ne retarde jamais une
réponse. Le fichier vit dans `HUB_USAGE_DB`, un volume en production.

La bibliothèque récupère `pipeline.toml` quand elle résout une référence
`catalog:` (dans `catalogs`, par `load_pipeline`, `RegexDetector.from_catalog`
ou `piighost.catalog.pull`), c'est donc ce chemin qui compte comme une
récupération, distinct de la simple lecture des métadonnées d'un objet.
