# Mesurer l'usage du catalogue

*[English version](en/analytics.md).*

Deux choses utilisent ce catalogue et une seule a un navigateur. Le site est
instrumenté depuis la page, où OpenPanel voit un appareil et une session.
L'autre est la bibliothèque piighost : elle récupère un `pipeline.toml` quand une
configuration de pipeline nomme une référence `catalog:` (`load_pipeline`,
`catalogs = [...]`) ou quand du code Python appelle `RegexDetector.from_catalog`
ou `piighost.catalog.pull`. Rien n'y charge de script, donc le seul endroit d'où
ses appels sont observables est la sortie de l'API.

D'où deux clients à créer dans le dashboard, et c'est la réponse à la question
qu'on se pose en arrivant :

| | Client navigateur | Client serveur |
|---|---|---|
| Qui parle | le site, depuis la page | l'API, pour la bibliothèque |
| Type OpenPanel | lecture/écriture, CORS ouvert | `write` |
| Identifiant | `clientId` seul | `clientId` **et** `clientSecret` |
| Où il vit | inliné dans le bundle, public | variable du service `api`, jamais dans le bundle |
| Variable | `VITE_OPENPANEL_CLIENT_ID` | `OPENPANEL_CLIENT_ID` + `OPENPANEL_CLIENT_SECRET` |

L'API track exige un client d'écriture, donc un secret, pour toute requête : un
id seul serait refusé sur chaque événement. C'est pour cela que le côté serveur
en demande deux et le côté navigateur un seul.

## Ce qui n'a pas changé, et c'est le but

La CSP reste `script-src 'self'; connect-src 'self'`. Deux décisions le
permettent :

- **Le SDK est bundlé** (`@openpanel/web`, 8 Ko) au lieu d'être chargé depuis
  `openpanel.dev`. Aucun script externe, donc rien à autoriser dans
  `script-src`. Le module d'enregistrement de session (rrweb, lourd) reste dans
  un chunk séparé qui n'est jamais demandé : on ne l'active pas.
- **L'ingestion passe par `/api/op`**, que nginx relaie vers l'instance
  auto-hébergée. Même origine, donc rien à autoriser dans `connect-src`.

Un effet de bord vaut autant que la CSP : un bloqueur de publicité qui coupe les
requêtes vers un domaine d'analytics n'a rien à reconnaître ici. Sans cela les
chiffres manqueraient la part des visiteurs qui en utilisent un, et on ne
saurait pas laquelle.

## Ce qui est envoyé

Côté navigateur, l'ensemble des événements est **fermé**, dans
`frontend/src/lib/analytics.ts`. Chaque propriété est une forme, un compte ou
une durée. Aucune ne peut porter un texte saisi, une valeur détectée ni un span.
Le site promet que le texte envoyé au bac à sable n'est jamais écrit en base ;
des analytics qui trahiraient cette promesse vaudraient moins que pas
d'analytics du tout. Ajouter une clé qui pourrait en porter une demande de
modifier ce type, dans un diff que quelqu'un relit.

Côté serveur, `backend/hub/analytics.py` envoie la forme de l'appel : le genre,
l'objet du registre nommé, si la référence était épinglée, et le statut.
L'adresse et le user agent de l'appelant ne sont **pas** transmis, bien
qu'OpenPanel les accepte et géolocaliserait avec.

Un appel venant d'un navigateur n'est pas transmis par le serveur : la page a
déjà envoyé son propre événement, et le compter deux fois rendrait faux chaque
chiffre du dashboard, d'une façon qui reste plausible.

## Rapport avec les compteurs sur disque

`backend/hub/usage.py` tient des compteurs dans un SQLite, et ce n'est pas la
même chose. Ils alimentent le nombre de `pull` affiché sur le site, sont
agrégés à l'heure par construction, et survivent sans dépendance extérieure.
OpenPanel donne ce qu'un tableau de bord donne : des séries, des entonnoirs, de
la rétention. On garde les deux, chacun pour ce qu'il fait.

## Mise en route

1. Dans le dashboard OpenPanel, créer le projet puis ses deux clients.
2. Renseigner `.env` d'après `.env.example` : `VITE_OPENPANEL_CLIENT_ID` pour le
   navigateur, les trois `OPENPANEL_*` pour le serveur, et `OPENPANEL_HOST` plus
   `SITE_URL` pour le relais nginx.
3. Reconstruire. `VITE_OPENPANEL_CLIENT_ID` est inliné au build par Vite, donc
   c'est un build arg : changer la variable sans reconstruire l'image ne change
   rien.

Sans ces variables, rien n'est chargé et rien n'est envoyé. C'est le défaut en
développement et pour quiconque héberge le catalogue lui-même.
