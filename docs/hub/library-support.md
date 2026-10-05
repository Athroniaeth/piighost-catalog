# Ce qui revient à `piighost`

*[English version](en/library-support.md).*

Le catalogue publie, vérifie et sert. Consommer une référence depuis un
déploiement revient à la bibliothèque, et ce travail vit dans son dépôt, pas
ici. Ce document fixe le contrat pour que les deux côtés puissent avancer
séparément, et dit ce que piighost 2.0 en livre.

Rien n'exige ce support : l'export **aplati** inline chaque regex, donc un
fichier téléchargé tourne sur un `piighost` 1.7 sans aucune modification. Le
support `catalog:` supprime l'étape de téléchargement, il ne débloque pas un
usage.

## Résoudre une référence dans `catalogs`

```toml
[detector]
type = "regex"
catalogs = ["catalog:piighost/generic", "catalog:alice/fr-extended:prod"]
```

Depuis la 2.0, `RegexDetectorConfig.catalogs` n'accepte que des références au
catalogue : piighost n'embarque plus de motif, et les anciens littéraux
(`generic`, `us`, `eu`, `fr`) sont refusés avec la référence qui les remplace.
Une référence est résolue **à la construction** (`build()`), jamais à la
validation, pour que `piighost validate` reste hors ligne et rapide. La fusion
ne change pas : les catalogues d'abord, dans l'ordre, puis les patterns en
ligne, ce qui est déjà l'ordre d'insertion que le catalogue garantit.

Le préfixe `hub:` des versions 1.x reste lu exactement comme `catalog:`.

## Depuis Python

```python
from piighost.components.detector import RegexDetector

detector = RegexDetector.from_catalog("piighost/logs:fd79aec6")
```

`RegexDetector.from_catalog` construit un détecteur depuis une référence, et
`piighost.catalog.pull` rend les regex d'une référence sous forme de
dictionnaire. Les noms 1.x restent des alias : `RegexDetector.from_hub` délègue
à `from_catalog`, et `piighost.hub` réexporte `piighost.catalog`.

## Charger une configuration entière

```python
from piighost.config import load_pipeline

pipeline = load_pipeline("catalog:alice/fr-default:prod")
```

`load_config`, `load_pipeline` et `load_thread_pipeline` acceptent un chemin ou
une référence `catalog:`, récupérée depuis
`/api/v1/refs/{ns}/{name}/{selector}/pipeline.toml` sous forme aplatie. Une
configuration du catalogue ne porte jamais de `[memory]`, donc
`load_thread_pipeline` la refuse ; l'appelant fournit sa mémoire, par la
surcharge d'environnement `PIIGHOST_MEMORY` ou par le chemin programmatique.

## Cache et miroir

Un commit est immuable, donc une référence épinglée par commit est gardée sur
disque, sous `~/.cache/piighost/catalog` (ou `$XDG_CACHE_HOME`), et récupérée
une seule fois. Un tag ou `latest` bouge, donc il est récupéré à chaque fois ;
l'API l'annonce déjà dans ses en-têtes.

| Variable | Rôle | Défaut |
|---|---|---|
| `PIIGHOST_CATALOG_URL` | URL de base, pour un miroir interne | `https://catalog.piighost.dev` |
| `PIIGHOST_HUB_URL` | ancien nom, lu quand `PIIGHOST_CATALOG_URL` est absent | non défini |

## Ce qui n'est pas livré

Le contrat prévoyait davantage, qui n'existe pas dans la 2.0. La bibliothèque
n'a pas de sous-commande de CLI pour le catalogue : ni `pull`, ni `lock`, ni
`verify`. Elle ne connaît ni `piighost.lock`, ni mode hors ligne, ni jeton pour
un miroir privé, ni dossier de cache configurable. Une configuration est de la
donnée déclarative, pas du code, mais une résolution réseau au démarrage reste
une dépendance : en attendant un lock, l'épinglage par commit et un miroir
interne sont les deux moyens qu'un déploiement n'en dépende pas au moment où il
démarre.

## Une limite que la bibliothèque seule peut lever

Deux motifs qui couvrent le même span sont départagés par l'ordre d'insertion,
puisque toute détection regex vaut une confiance de 1. Cela règle les spans
identiques, pas les spans différents mais chevauchants : sur `01.99.00.12.34`,
une IPv4 qui commence au même endroit mais finit plus tôt l'emporte sur le
téléphone français, quel que soit l'ordre. Le catalogue a contourné ce cas en
resserrant son motif IPv4, ce qui était de toute façon correct, mais le levier
général, une priorité par motif dans `RegexDetector`, est du côté de la
bibliothèque.
