# Format des manifestes

*[English version](en/manifest.md).*

Le registre est un arbre de fichiers TOML. Chaque objet publiable, motif, groupe
ou config, vit dans son dossier avec un manifeste et, s'il porte des tags
mobiles, un fichier `tags.toml`. Ce document décrit chaque fichier. La façon dont
ils se résolvent en commits et en pipelines est dans [resolution.md](resolution.md).

```
registry/
  vocabulary.toml                 vocabulaire fermé des tags
  patterns/<ns>/<name>/pattern.toml
  groups/<ns>/<name>/group.toml
  configs/<ns>/<name>/config.toml
  samples/<name>/sample.toml      textes annotés, non versionnés
  <kind>/<ns>/<name>/tags.toml    pointeurs de tags, facultatif
  commits/<ns>/<name>/<short>.json  instantanés immuables, écrits par `hub record`
```

Règles communes :

- `schema_version = 1` en tête de chaque manifeste. C'est la version du format,
  jamais celle de l'objet : la version d'un objet est son commit, elle ne
  s'écrit pas dans le fichier.
- Un espace de noms et un nom sont en kebab-case (`^[a-z0-9][a-z0-9-]*$`). Le
  nom du manifeste doit égaler le nom de son dossier.
- Une clé inconnue est une erreur, pas un avertissement.
- Les tags sont une liste à plat, mais chaque tag doit exister dans
  `vocabulary.toml`.
- Les descriptions sont bilingues, `{ en = "...", fr = "..." }`.

## `vocabulary.toml`

Un tag par table. `kind` sert au site à dériver ses facettes, l'auteur d'un
manifeste n'a pas à le connaître.

```toml
[fr]
kind = "region"
label = { en = "France", fr = "France" }

[government-id]
kind = "category"
label = { en = "Government identifier", fr = "Identifiant d'État" }
```

Les `kind` en usage : `region`, `category`, `domain`, `use-case`, `language`.
Trois familles ne se tapent pas, elles se déduisent : officiel ou communautaire
vient de l'espace de noms, regex seul ou modèle local ou clé d'API vient du
contenu d'une config, retiré vient du statut d'un commit.

## `pattern.toml`

Un regex, un label, ses exemples.

```toml
schema_version = 1

[pattern]
name = "fr-nir"
label = "FR_NIR"
tags = ["fr", "government-id", "health"]
regex = '\b[12][\s.-]?\d{2}[\s.-]?(?:0[1-9]|1[0-2])[\s.-]?(?:2A|2B|\d{2})[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{2}\b'
resilience = true          # facultatif, défaut true

[pattern.description]
en = "French social security number (NIR). Shape only, no checksum."
fr = "Numéro de sécurité sociale français (NIR). Forme seule, sans clé."

[[examples.match]]
text = "NIR : 1 85 05 78 006 084 36."
value = "1 85 05 78 006 084 36"

[[examples.no_match]]
text = "180137505600157"

[redos]                    # facultatif
prefix = "1 85 01 "
filler = "75 "
suffix = "x"
```

| Clé | Règle |
|---|---|
| `label` | `^[A-Z][A-Z0-9_]*$`, le label que le détecteur émet |
| `regex` | Python `re`, compilé avec `re.ASCII`, sans autre drapeau. Un drapeau inline comme `(?i)` s'écrit dans le motif. Chaîne littérale TOML `'...'` de préférence, pour garder les antislashs simples |
| `examples.match` | au moins un. `value` est la sous-chaîne exacte attendue et doit apparaître exactement une fois dans `text` |
| `examples.no_match` | au moins un. Le motif ne doit rien détecter dans `text` |
| `resilience` | quand vrai, chaque `value` est aussi testée enveloppée de ponctuation adjacente (`{v}.`, `{v},`, `{v}\n`, ` {v} `, `({v})`, `Reach me at {v}.`) et doit être détectée seule et entière |
| `redos` | recette adverse : un préfixe valide, un fragment ambigu répété jusqu'à 100 000 caractères, une fin qui interdit le match. Sans recette, huit fragments génériques sont essayés |

Les exemples sont synthétiques, sans exception : domaines réservés
(`example.com`), plages de documentation (RFC 5737 pour IPv4, RFC 3849 pour
IPv6, 555-01xx pour les numéros américains), IBAN et cartes de test, identifiants
inventés. Aucune valeur réelle, même publique.

## `group.toml`

Un groupe ne contient aucun regex. Il compose des références dans un ordre, avec
une exclusion par source.

```toml
schema_version = 1

[group]
name = "fr-notariat"
description = { en = "French notarial deeds", fr = "Actes notariés français" }
tags = ["fr", "notarial"]

[[sources]]
ref = "piighost/fr-siret"

[[sources]]
ref = "piighost/fr"
exclude = ["FR_PHONE"]

[[sources]]
ref = "piighost/generic"
only = ["EMAIL", "URL"]
```

| Clé | Règle |
|---|---|
| `sources` | au moins une entrée, dans l'ordre d'insertion voulu |
| `sources[].ref` | un motif ou un groupe, avec tag, commit ou nu (`latest`) |
| `sources[].exclude` | labels de cette source à écarter ; chacun doit exister dans la source |
| `sources[].only` | labels de cette source à garder, exclusif avec `exclude` |

Un motif est un groupe d'un seul label, donc une source peut être l'un ou
l'autre. Il n'existe pas d'exclusion globale après fusion : tout se dit dans le
bloc de la source concernée.

## `config.toml`

Une config décrit un pipeline piighost sans ses sections de déploiement. Ses
détecteurs portent un nom, ce qui donne une prise à l'héritage.

```toml
schema_version = 1

[config]
name = "fr-default"
description = { en = "French default", fr = "Défaut français" }
tags = ["fr", "chat"]
piighost = ">=2.0,<3"

[[extends]]
ref = "piighost/regex-default"
exclude = ["detector:regex-us", "label:CREDIT_CARD", "stage:guard"]

[[detectors]]
name = "regex-fr"
type = "regex"
groups = ["piighost/fr-extended", "piighost/eu"]

[[detectors]]
name = "ner-fr"
type = "gliner2"
model = "fastino/gliner2-multi-v1"
labels = ["PERSON", "ADDRESS"]
threshold = 0.5

[stages.expander]
type = "word_boundary"

[stages.anonymizer.placeholder]
type = "label_counter"
```

| Clé | Règle |
|---|---|
| `piighost` | un spécificateur de version PEP 440, facultatif mais recommandé ; le check refuse de valider une config contre une version qu'elle exclut |
| `extends[].ref` | une config parente |
| `extends[].exclude` | préfixé : `detector:<nom>`, `label:<LABEL>`, `stage:<section>` ; chaque cible doit exister chez le parent |
| `detectors[].name` | kebab-case, unique dans la config et parmi les détecteurs hérités |
| `detectors[].type` | un type de détecteur piighost. Les autres clés sont passées telles quelles à piighost, qui les valide |
| `detectors[]` de type `regex` | porte `groups`, une liste de références, et rien d'autre. Un regex inline contournerait les motifs testés |
| `stages` | une table par section piighost : `linker`, `anonymizer`, `overlap_resolver`, `expander`, `entity_resolver`, `guard`, `override`, `observation_redactor`. Passée telle quelle |
| `memory`, `token_memo_ttl` | refusés : l'exploitant les ajoute à l'export ou au chargement |

## `tags.toml`

Les pointeurs mobiles d'un objet, posés par le propriétaire de l'espace de noms.

```toml
prod = "3fa9c2e1"
preprod = "9c8e7f6a"
```

Un tag est en kebab-case, n'est pas `latest`, et n'est pas composé uniquement de
caractères hexadécimaux. Il pointe un commit enregistré dans `commits/`. Le tag
`latest` n'y figure jamais : il est calculé et désigne toujours la tête de
travail.

## `sample.toml`

Un texte annoté. Les samples alimentent le bac à sable et servent de corpus de
mesure. Ce sont des données, pas des artefacts publiés : personne n'épingle un
sample, donc contrairement à un motif il ne porte ni commit ni tag, et il vit
dans un seul espace de noms.

```toml
schema_version = 1

[sample]
name = "email-pro-fr"
title = { en = "Business email (French)", fr = "E-mail professionnel (français)" }
tags = ["fr", "lang-fr", "customer-support"]
text = """
Bonjour, je suis joignable au 06 39 98 12 34.
"""

[[annotations]]
value = "06 39 98 12 34"
label = "FR_PHONE"
```

| Clé | Règle |
|---|---|
| `text` | le texte, en chaîne multiligne |
| `annotations[].value` | une valeur qu'un bon pipeline doit attraper ; elle doit apparaître dans le texte |
| `annotations[].label` | le label attendu, en UPPER_SNAKE |

L'annotation se fait par valeur et non par position : une position casse dès
qu'on corrige une faute de frappe dans le texte, et chaque occurrence d'une
valeur annotée est attendue.

Les mêmes règles de synthèse s'appliquent qu'aux motifs. Un sample annoté
`PERSON` sur un nom inventé est utile même si aucun motif regex ne le trouve :
c'est ce qui montre ce qu'une configuration sans modèle laisse passer.
