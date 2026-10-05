# Références, commits et résolution

*[English version](en/resolution.md).*

Ce document fixe ce qu'une référence désigne, comment un objet devient un commit
immuable, et comment un groupe ou une config se résout en pipeline piighost. Le
format des fichiers est dans [manifest.md](manifest.md), l'API HTTP dans
[api.md](api.md).

## Références

```
catalog:alice/fr-notariat:prod            tag, mobile, posé par le propriétaire
catalog:piighost/fr-notariat:3fa9c2e1     commit, immuable
catalog:piighost/fr-notariat:latest       tag calculé, dernier commit
catalog:piighost/fr-notariat              équivaut à :latest
```

Un seul séparateur sert aux tags et aux commits. La règle de désambiguïsation est
syntaxique : huit caractères hexadécimaux exactement désignent un commit, tout le
reste est un tag. En contrepartie un tag ne peut pas être composé uniquement de
caractères hexadécimaux, ni s'appeler `latest`. Le préfixe `catalog:` est
facultatif dans un manifeste, où toute référence désigne un objet du catalogue,
et d'usage dans un fichier piighost, où il marque une référence au catalogue.
L'ancien préfixe `hub:` reste accepté partout, ici comme dans la bibliothèque.

## Commits

Un commit est un contenu, pas un numéro. À la publication, chaque référence du
manifeste est résolue en commit, le manifeste ainsi figé est sérialisé en JSON
canonique (clés triées, sans espace, UTF-8 conservé), et son sha256 est calculé.
Les huit premiers caractères forment l'identifiant court, scopé à un objet.

Conséquences :

- Un commit est immuable par construction : changer une virgule donne un autre
  hash. Reformater ou commenter le fichier n'en crée pas, la forme canonique
  ignore commentaires et ordre des clés.
- Le hash d'un groupe couvre transitivement ses sources : changer un motif change
  le commit de tout groupe et de toute config qui l'atteignent.
- L'historique ne fait que croître. Un commit fautif se marquera déprécié avec un
  message, il ne se supprime pas.

Les commits sont enregistrés sous `commits/<ns>/<name>/<short>.json`, avec leur
digest complet et leur date. `hub check` recalcule chaque digest et échoue sur un
fichier modifié : c'est ainsi qu'une réécriture est détectée. L'historique vit
dans ces fichiers, pas dans git, donc une ingestion n'a pas besoin de `git log`
et un miroir est une simple copie.

La tête de travail d'un objet est le commit que son manifeste actuel produirait.
`hub check` exige qu'elle soit enregistrée ; `hub record` enregistre celles qui
ne le sont pas. Dans ce registre monodépôt, publier revient donc à pousser un
manifeste puis lancer `record`, et une référence nue (`latest`) suit la tête à
chaque passage, ce que la CI teste dans son ensemble.

## Tags

Un tag est un pointeur mobile, propriété de l'éditeur de l'espace de noms.
`latest` est calculé et pointe toujours la tête, personne ne le déplace à la
main. Les autres, `prod`, `preprod`, ce que vous voulez, vivent dans le
`tags.toml` de l'objet et se déplacent par un commit git, ce qui laisse une
trace. Un tag doit pointer un commit enregistré.

L'espace de noms `piighost` n'en pose aucun, volontairement. Un objet officiel
n'a donc que `latest` et ses commits : ce qui est publié est ce qui est servi,
et une équipe qui veut un palier de recette le tient chez elle, dans son propre
espace de noms, où elle décide seule quand `prod` bouge. Le mécanisme existe
pour les autres, pas pour nous.

Un auteur écrit des tags dans ses manifestes ; la publication les fige en
commits et stocke les deux, la référence écrite et le commit résolu :

```json
{"ref": "alice/fr-base:prod", "commit": "b41d09aa", "exclude": ["FR_PHONE"], "only": []}
```

Un groupe ne suit donc jamais silencieusement le `prod` de ses parents entre
deux publications.

## Résolution d'un groupe

Un groupe se résout en un dictionnaire ordonné label vers regex, la forme exacte
d'un catalogue piighost, augmenté de la provenance de chaque label. Trois
règles :

1. **Un label venant de deux sources est une erreur.** L'auteur tranche en
   l'excluant de l'une des deux, dans son bloc, ou avec `only`. Aucun écrasement
   silencieux n'existe. Seule exception : le même commit de motif atteint par
   deux chemins, un losange inoffensif, qui est simplement dédoublonné.
2. **`exclude` et `only` doivent nommer des labels que la source fournit.** Une
   faute de frappe est une erreur, pas un silence.
3. **L'ordre des sources est l'ordre d'insertion dans le détecteur.** Tous les
   regex valent une confiance de 1, et le resolver de piighost trie par confiance
   puis par span avec un tri stable : sur deux spans identiques, le premier
   inséré gagne. Le catalogue n'ajoute aucune règle, il respecte l'ordre.

Sur la troisième règle, un cas réel : un SIRET de quatorze chiffres est aussi une
carte bancaire de forme (treize à dix-neuf chiffres). Avec `generic` déclaré
avant `fr`, `73282932000074` sort en `<<CREDIT_CARD:1>>`. Le test de composition
le signale et l'auteur réordonne. Un span différent mais chevauchant se règle
toujours par la position, pas par l'ordre : un IBAN entier l'emporte sur les
seize chiffres qu'il contient.

## Composer plusieurs pays

Un groupe national est fait pour être utilisé seul, ou avec des groupes d'une
autre nature. Les empiler tels quels ne marche pas, et la raison est de forme,
pas d'implémentation : les identifiants nationaux se ressemblent.

Un code postal fait cinq chiffres en France, en Allemagne, en Espagne, en
Italie et aux États-Unis. Un numéro à neuf chiffres est un routage bancaire
américain, un BSN néerlandais et un SIN canadien. Dix chiffres nus sont un
numéro NHS, un NPI américain et un Medicare australien. Sur un span identique,
c'est la première source déclarée qui gagne, donc mettre deux pays dans un même
détecteur revient à étiqueter les valeurs du second avec les labels du premier.

Trois façons de s'en sortir, par ordre de préférence :

1. **Un détecteur par pays.** Une config peut en porter plusieurs, et le
   resolver tranche entre eux comme entre deux motifs. C'est ce que fait
   `regex-default` avec `fr`, `eu`, `us` et `generic`. Cela ne supprime pas la
   collision, cela la rend visible et ordonnée.
2. **Exclure la forme ambiguë** dans le bloc de la source, avec `exclude`. Un
   groupe multi-pays qui garde un seul code postal et écarte les autres est
   honnête : il dit quel pays il sert vraiment.
3. **Ne pas mélanger.** Une config nommée d'après un pays est plus utile qu'une
   config qui prétend couvrir le monde et se trompe d'étiquette une fois sur
   deux.

Cette règle a été éprouvée plutôt que supposée. Un groupe `eu-countries`
composant la France, l'Allemagne, l'Espagne, l'Italie, les Pays-Bas et la
Pologne a été écrit, puis refusé par le check avec neuf collisions : le code
postal allemand réclame les codes espagnol et italien, le téléphone espagnol
réclame le BSN néerlandais et le téléphone polonais, le numéro de TVA italien
réclame le PESEL. Ce groupe n'existe pas, et ne peut pas exister.

Les groupes par concept, eux, marchent quand leurs membres ont des formes
distinctes, et le check dit lesquels. `payment`, `contact` et
`identity-documents` passent tels quels. Trois autres ont demandé un
arbitrage, chacun consigné dans la description du groupe : `business` écarte le
NIF portugais, neuf chiffres nus qui réclament la tête d'un SIRET ; `health`
écarte le numéro de praticien américain, dix chiffres nus indiscernables du
numéro NHS ; `logs` écarte l'URL, qui avale un jeton inscrit dedans.

## Qui gagne un span, exactement

Le resolver trie par `(-confiance, span)` et garde gloutonnement. La confiance
d'un regex vaut toujours 1, donc c'est le span seul qui décide, et un span est
un couple `(début, fin)` trié en ordre croissant. Deux conséquences, et les deux
surprennent :

- **Le span qui commence le plus tôt gagne.** C'est l'intuition habituelle.
- **À début égal, c'est le plus court qui gagne**, pas le plus long. Un motif
  qui reconnaît le *début* d'une suite plus longue la découpe donc au lieu de
  lui céder la place.

C'est cette seconde règle qui casse le plus de motifs, et toujours de la même
façon : un téléphone danois de huit chiffres se pose sur la tête d'un numéro de
carte de seize, un Aadhaar de douze chiffres groupés aussi, un code postal
japonais sur la tête d'un téléphone japonais. Le remède n'est pas l'ordre des
sources, qui ne joue qu'à span identique, mais le motif lui-même : une
anticipation négative de fin qui refuse un séparateur suivi d'un chiffre.

```
(?<!\w)\d{3}-\d{4}(?!\w)(?![\s.-]?\d)
```

Un code postal japonais écrit ainsi ne réclame plus `090-1234` dans
`090-1234-5678`. Sept motifs du registre portent cette anticipation, tous
ajoutés après que le check de composition les a pris en faute.

Quand les deux spans sont *identiques*, en revanche, seul l'ordre des sources
tranche, et la règle est de déclarer le plus spécifique d'abord. Quatre groupes
le font, chacun avec sa raison écrite dans sa description : `us` place le numéro
fiscal individuel avant le numéro de sécurité sociale, qui ne commence jamais
par 9 ; `business` place le numéro de TVA britannique avant l'européen, le
Royaume-Uni ayant quitté ce système ; `health` place le CPR danois avant le
numéro NHS, sa date de naissance validée étant plus spécifique ; `international`
place l'ORCID avant le numéro de carte, aucune carte ne commençant par 0000.

Ce qui se compose sans risque, en revanche, ce sont les groupes qui ne reposent
pas sur une longueur de chiffres : `generic`, `international`, `secrets`,
`secrets-extended`, `network`, `crypto`. Leurs formes portent un préfixe, un
séparateur ou un alphabet qui les distingue, donc ils s'ajoutent à n'importe
quel pays.

Le check de composition rejoue les exemples de chaque motif retenu contre
l'ensemble aplati, donc une collision entre deux pays fait échouer la
publication plutôt que d'arriver chez un utilisateur.

## Résolution d'une config

Une config se résout en une liste ordonnée de détecteurs nommés et une table
d'étages, avec la même discipline :

- Les détecteurs des parents, dans l'ordre des `[[extends]]`, puis ceux de la
  config elle-même. Un nom présent deux fois est une erreur : on exclut chez le
  parent (`detector:<nom>`) ou on renomme.
- `label:<LABEL>` retire un label des détecteurs regex hérités de ce parent. Le
  label doit exister chez le parent ; vider complètement un détecteur est une
  erreur, on exclut alors le détecteur.
- Un étage écrit dans l'enfant remplace l'étage du parent en bloc, sans fusion
  clé par clé : une fusion de `threshold` ou de `labels` produirait une config
  que personne n'a écrite. Deux parents fournissant le même étage est une
  erreur, réglée par `stage:<section>`.
- Un détecteur regex qui liste plusieurs `groups` les fusionne avec la règle des
  groupes : un label commun est une erreur, sauf losange.

## Rendu

Le rendu produit un fichier piighost. Un seul détecteur est écrit tel quel,
plusieurs deviennent un `composite` dans l'ordre. Deux formes :

- **aplatie**, par défaut : chaque détecteur regex reçoit `patterns = { LABEL =
  '...' }` dans l'ordre résolu. Le fichier fonctionne hors ligne, sur toute
  version de piighost qui accepte ses sections, sans support du catalogue.
- **référencée** (`keep_refs`) : `catalogs = ["catalog:piighost/fr:3fa9c2e1"]`,
  pour un piighost qui résout lui-même, ce que fait la 2.0. Voir plus bas.

Le champ `name` du pipeline reçoit la référence rendue, `ns/name:short`, pour la
traçabilité. Les regex sont écrits en chaînes littérales TOML quand ils ne
contiennent pas d'apostrophe, ce qui évite le double échappement. La mémoire
n'est jamais dans une config partagée ; l'option `memory` ajoute une section
depuis un préréglage (`in_memory`, `redis` avec hacheur Argon2 et chiffrement
AES-GCM, `sqlalchemy` idem), à compléter par l'exploitant.

Chaque config rendue est validée par le `PipelineConfig` du piighost installé,
sans construire de composant : aucun modèle ne charge.

## Checks

`python -m backend.hub check` enchaîne, sur les têtes de travail :

| Check | Sujet | Échoue quand |
|---|---|---|
| Structure | manifestes | clé inconnue, nom ou label mal formé, regex non compilable, tag hors vocabulaire, `value` absente ou multiple, `exclude` avec `only` |
| Exemples | motifs | un `match` n'est pas détecté comme sa valeur, un `no_match` l'est |
| Résilience | motifs | une valeur enveloppée de ponctuation n'est pas détectée seule et entière |
| Composition | groupes, configs | un exemple d'un motif gardé n'est plus détecté sous son label une fois composé, volé par un voisin sur le même span ou avalé par un plus large |
| Borne de backtracking | motifs | un balayage de 100 000 caractères adverses dépasse 0,25 s, ou ne termine pas en 5 s (le processus est tué) |
| Rendu | configs | piighost rejette le pipeline rendu, ou la config déclare une plage piighost qui exclut la version installée |
| Store | commits | un instantané ne correspond plus à son digest |
| Tags | pointeurs | un tag pointe un commit inconnu |
| Enregistrement | têtes | une tête n'est pas enregistrée (`record` la corrige) |

Tous les checks tournent avec les vrais composants piighost, `RegexDetector` et
`ConfidenceOverlapResolver`, jamais une réimplémentation.

## Ce qui revient à la bibliothèque

Le catalogue publie et vérifie. Consommer une référence depuis un déploiement
revient à `piighost`, qui le fait depuis la 2.0 sans ligne de commande dédiée :
une référence `catalog:` dans `catalogs` ou passée à `load_pipeline`, ou
`RegexDetector.from_catalog` et `piighost.catalog.pull` depuis Python. Chacun
récupère `pipeline.toml` depuis l'API, et une référence épinglée par commit est
mise en cache sur disque. L'ordre des motifs y est l'ordre d'insertion. Le détail,
et ce qui n'est pas livré (lock, vérification, mode hors ligne), est dans
[library-support.md](library-support.md).
