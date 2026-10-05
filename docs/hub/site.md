# Le site

*[English version](en/site.md).*

Une application Svelte servie par nginx, qui parle à l'API sous `/api/v1` en
origine unique. Huit routes, aucun état côté serveur, aucun compte. Chaque route
vit sous sa langue, `/en/...` et `/fr/...`. Le tableau les nomme sans le
préfixe.

| Route | Ce qu'on y fait |
|---|---|
| `/` | le catalogue : recherche, tri, liste d'objets, facettes à cocher |
| `/r/:ns/:name[/:selector]` | une fiche : historique des commits à gauche, onglets Contenu, Fichier de pipeline, L'utiliser à droite |
| `/playground` | lancer un objet ou un regex candidat sur un texte |
| `/playground/compare` | deux à quatre objets sur le même texte |
| `/playground/chat` | l'aller-retour complet, avec un assistant scripté |
| `/contribute` | rédiger un motif ou un groupe en deux colonnes, l'essayer et le vérifier depuis le pied de la seconde |
| `/labels` | les labels que le catalogue peut émettre, depuis le pied de page |
| `/stats` | comment le catalogue est utilisé, depuis des compteurs agrégés à l'heure |

## Structure, d'après le LangSmith Hub

La disposition reprend celle du [LangSmith Hub](https://smith.langchain.com/hub),
qui distribue des prompts comme ce site distribue des configurations, et dont
les visiteurs de `piighost` connaissent déjà les gestes.

- **Une barre de fil d'Ariane, pas une barre de navigation.** La marque, puis la
  place de la page dans le registre, `piighost / fr-default`. À droite, les deux
  actions qu'un visiteur entreprend, le bac à sable et la contribution, puis
  GitHub, le thème et la langue.
- **Un titre centré et une recherche en pilule.** La page d'accueil est le
  catalogue : un titre, une ligne, un champ de recherche large, et tout de suite
  la liste.
- **Des chips de tri.** Couverture la plus large, pertinence, mis à jour
  récemment, les plus utilisés, nom. Sans requête, l'ordre par défaut est la
  couverture : quelqu'un qui arrive sans rien taper cherche ce qui couvre le
  plus, pas ce qu'un mainteneur a touché en dernier. Dès qu'une requête est
  tapée, la pertinence reprend la main.
- **Une liste verticale, pas une grille.** Chaque ligne porte ses pastilles en
  tête (le type, puis les tags), la référence en titre, la description sur deux
  lignes, puis une ligne de métadonnées : date de mise à jour, nombre de labels,
  de commits et d'utilisations. Un bouton « Essayer » à droite mène au bac à
  sable avec l'objet préchargé.
- **Des facettes à cocher avec compteurs**, dans une colonne à droite, groupées
  par famille : type, région, catégorie, métier, cas d'usage, langue. Les
  familles viennent du `kind` du vocabulaire, les auteurs de manifestes ne les
  voient jamais.
- **Une fiche en deux colonnes.** À gauche, l'historique des commits, chaque
  carte portant son hash, ses tags pointeurs et sa date. À droite, le commit
  affiché avec ses pointeurs, puis des onglets : Contenu, Fichier de pipeline,
  L'utiliser. La barre de titre porte la référence, les pastilles,
  et trois actions : copier la référence, télécharger, essayer.

## Charte

Le site reprend la charte de `piighost-studio` pour que l'écosystème se lise
d'un seul tenant : l'échelle neutre de shadcn, un seul violet primaire, Geist
pour le texte et Geist Mono pour le code et la marque, un rayon de base de
0,625 rem. Le clair est le défaut et le sombre est une classe sur `<html>`
posée par le visiteur, jamais déduite du système, comme le studio le fait.

Les polices sont auto-hébergées par `@fontsource-variable/geist`, la CSP ne
laissant aucune autre origine. Les icônes viennent de lucide, une par import.

**Trois surfaces, une grammaire.** Le bac à sable, la comparaison, le chat et
la page de contribution sont une même carte en trois colonnes numérotées,
Configurer, Texte, Résultats, avec un en-tête de région identique. C'est le
composant `Region` qui porte cette grammaire, et les quatre pages l'importent.

**Contribuer se fait par formulaire.** Un motif, un groupe et une configuration
ont chacun le leur ; la configuration retombe sur l'éditeur TOML quand elle
porte ce que le formulaire ne sait pas réécrire, un détecteur à modèle ou un
étage hors des trois standards, en nommant la pièce en cause. Chaque exemple
d'un motif porte son verdict en direct, rendu par le moteur Python qui
l'exécutera, parce qu'un navigateur ne peut pas répondre honnêtement à cette
question.

**La configuration ne se contribue pas ici.** Un motif et un groupe ont chacun
leur formulaire ; la configuration en a eu un, complet et testé, puis il a été
retiré. Assembler des détecteurs et des étages de traitement est une interface
plus grande qu'un formulaire, et le chemin visé passe par une conversation
plutôt que par une grille de sélecteurs. Le formulaire existant est conservé à
l'étiquette git `config-form/v1`, avec dans son message les fichiers à
restaurer. L'API, elle, accepte toujours une soumission de type `config`.


**Les couleurs d'entités sont celles du studio.** Une palette de quinze teintes
attribuée par ordre d'apparition, `PERSON` sur le primaire, portée
verbatim de `labels.ts`. Un label garde donc la même couleur dans le catalogue et
dans le bac à sable du studio.

**Les composants.** Sous `components/ui/` : `Button`, `Badge`, `Card`,
`Segmented`, `Tabs`, `Region`, `StepChip`, `CodeBlock`, `CopyButton`. Au-dessus :
`EntityLabel`, `EntityRow`, `EntityHighlight`, `ObjectCard`, `RefPicker`,
`SamplePicker`, `SiteNav`, `SiteFooter`. Les contrôles natifs partagent leurs
classes depuis `lib/ui.ts` plutôt qu'un composant par champ.

## Choix qui se voient

**Les filtres vivent dans l'URL.** Une vue filtrée doit être partageable, et le
bouton retour doit défaire un filtre plutôt que quitter la page. Le catalogue lit
donc `q`, `kind`, `tag` (répétable) et `label` depuis la query, et n'a pas d'état
propre.

**Deux langues, jusque dans les manifestes.** Chaque page existe sous `/en/` et
`/fr/`, le schéma vers lequel pointent tous les sites piighost, et le menu de
langue de l'en-tête mène à la même page dans l'autre langue. Une URL sans
préfixe, `/` ou l'ancien `/r/piighost/generic`, est envoyée par nginx vers le même
chemin sous la langue du navigateur (le français quand `Accept-Language` le met
en premier, l'anglais sinon), par une 302 puisque la réponse dépend de qui
demande. Le routeur fait de même depuis `navigator.language` là où nginx n'est
pas devant. Chaque page porte son `lang`, son URL canonique et ses alternates
`hreflang`, écrits par le prérendu et tenus à jour par le routeur après une
navigation, et le sitemap liste les deux langues. Une description est bilingue dans
le manifeste, `en` obligatoire et `fr` facultatif : une page française montre
l'anglaise là où il n'y a pas de français, et la marque `lang="en"`.

**Deux colonnes, et deux dialogues.** La page en a porté trois : identité,
contenu, constats. La troisième ne servait qu'à deux moments, lire le résultat
d'une vérification et essayer un groupe, et elle écrasait les deux autres le
reste du temps. Ce qui reste manquant s'affiche au pied de la deuxième colonne,
au-dessus des boutons ; le résultat d'une vérification et l'essai sont des
`<dialog>` natifs. Le top layer évite au passage le rognage que la carte impose
à tout ce qui déborde, deux fois appris sur ce projet.

**Un groupe s'essaie sans être publié, et sans envoyer le texte.** Le bouton
« Lancer ici » aplatit les sources par l'API, parce que décider ce qui arrive
quand deux sources portent un même label est la règle du registre et qu'il ne
doit en exister qu'une implémentation. Puis il exécute le résultat avec piighost
lui-même, compilé en WebAssembly par Pyodide, dans l'onglet. Le catalogue est
public ; le texte ne l'est pas, et il ne part nulle part.

C'est ce qui justifie la seule concession de la CSP, `wasm-unsafe-eval` dans
`script-src`. Le nom fait peur et la portée ne l'est pas : elle autorise la
compilation WebAssembly, pas `eval`, pas `new Function`, pas le script en ligne.
Pyodide et le wheel sont servis depuis cette origine, jamais depuis un CDN ni
depuis PyPI, donc `connect-src 'self'` ne bouge pas non plus.

**Aucun style en ligne.** La CSP de production autorise `style-src 'self'` sans
`unsafe-inline`. Une coloration syntaxique qui émettrait `style="color:…"`
marcherait en développement et casserait en production, donc la coloration passe
par des classes et les couleurs vivent dans la feuille de style. Le bundle
construit ne contient aucun attribut `style`.

**Une fiche imprimable.** La classe `no-print` retire les contrôles, et la
feuille bascule en noir sur blanc. Un DPO lit une fiche de couverture sur
papier, pas un fichier TOML.

**Un routeur en un fichier.** Huit routes, pas de layouts imbriqués : une
dépendance de routage coûterait plus en indirection qu'elle n'apporte. nginx
sert déjà `index.html` en repli, ce dont un routeur d'historique a besoin. Les
liens restent de vrais `<a href>`, donc le clic du milieu et l'ouverture dans un
onglet marchent.

## Ce que le bac à sable ne fait pas

Les détecteurs à modèle, GLiNER2 et spaCy, ne tournent pas : il faudrait
télécharger et charger des poids à chaque requête. Une configuration qui en
porte un est quand même exécutable, ses détecteurs regex tournent, et la réponse
nomme ce qui a été sauté dans `unsupported`. La fiche le dit aussi.

Faire tourner un modèle dans le navigateur via Pyodide, comme le site de
présentation de `piighost` le fait, reste la bonne réponse à terme : le texte ne
quitterait pas la machine, ce qui est exactement l'argument pour un outil de PII.
C'est une application à part entière, pas une case à cocher ici.
