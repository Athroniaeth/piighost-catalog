/**
 * Two languages, one dictionary, no dependency.
 *
 * The catalog is bilingual down to each manifest, so the site is too: every
 * page lives under /en/ and /fr/, and the router sets the locale from the path.
 * A missing key falls back to English rather than rendering the key itself.
 * Copy follows the studio's rules: no em-dash, correct French accents, and in
 * French a no-break space (U+00A0) before : ; ? ! so the sign never starts a
 * line on its own.
 */

export type Locale = "en" | "fr";

const STRINGS = {
  en: {
    "nav.catalogue": "Catalog",
    "nav.playground": "Playground",
    "nav.contribute": "Contribute",
    "nav.github": "GitHub",
    "nav.theme": "Toggle theme",
    "nav.language": "Change language",
    "nav.skip": "Skip to content",
    "nav.menu": "Menu",
    "nav.main": "Main navigation",

    "home.title": "piighost catalog",
    "home.lede":
      "Explore and contribute tested de-identification regexes: single patterns, and the groups that compose them.",
    "home.search": "Search patterns, groups, labels, tags...",
    "home.all": "All",
    "home.patterns": "Patterns",
    "home.groups": "Groups",
    "home.configs": "Configurations",
    "home.empty": "Nothing matches these filters.",
    "home.clear": "Clear",
    "home.usedBy": "used by",
    "home.tryIt": "Try it",
    "home.playground":
      "Have a text to check? Run it through any pattern in the",
    "home.updated": "Updated",
    "home.never": "unrecorded",
    "home.sort": "Sort",
    "home.sort.relevance": "Relevance",
    "home.sort.updated": "Recently updated",
    "home.sort.used": "Most used",
    "home.sort.labels": "Widest coverage",
    "home.sort.pulls": "Most pulled",
    "home.sort.name": "Name",
    "home.page": "Page",
    "home.previous": "Previous",
    "home.next": "Next",
    "facet.type": "Type",
    "facet.more": "Show more",
    "facet.less": "Show less",
    "facet.region": "Region",
    "facet.category": "Category",
    "facet.domain": "Domain",
    "facet.use-case": "Use case",
    "facet.language": "Language",
    "detail.content": "Content",
    "detail.history": "Commit history",
    "detail.copyRef": "Copy the reference",
    "detail.tryIt": "Try it",
    "detail.unrecorded": "unrecorded head",

    "kind.pattern": "pattern",
    "kind.group": "group",
    "kind.config": "piighost config",

    "pick.filter": "Filter by name, label or tag",
    "pick.none": "Nothing matches.",

    "detail.openPlayground": "Open in the playground",
    "detail.download": "Download TOML",
    "detail.pipeline": "Pipeline file",
    "detail.flattened": "Inlined",
    "detail.referenced": "By catalog id",
    "detail.pullsWindow": "Over the last thirty days",
    "detail.memory": "Memory",
    "detail.part": "Scope",
    "detail.wholePipeline": "Whole pipeline",
    "detail.detectorOnly": "Detector only",
    "detail.detectorNote":
      "The detector alone, to paste into a pipeline you already have. The linker, the anonymizer and the memory stay yours.",
    "detail.none": "none",
    "detail.use": "Use it",
    "detail.commits": "Commits",
    "detail.pattern": "Pattern",
    "detail.engine": "Python re, ASCII",
    "detail.matches": "Must match",
    "detail.noMatches": "Must not match",
    "detail.sources": "Sources",
    "detail.sourcesNote":
      "Insertion order. On an identical span the first source wins.",
    "detail.labels": "Labels",
    "detail.detectors": "Detectors",
    "detail.from": "from",
    "detail.excluded": "excluded",
    "detail.only": "only",

    "play.run": "Run",
    "play.compare": "Compare",
    "play.chat": "Chat",
    "play.configure": "Configure",
    "play.text": "Text",
    "play.results": "Results",
    "play.object": "Object",
    "play.candidate": "Regex",
    "play.candidateNote":
      "Not in the catalog. Runs in a separate process, killed after two seconds.",
    "play.regexPlaceholder": "A regex to try",
    "play.sample": "Load a sample",
    "play.go": "Run",
    "play.running": "Running",
    "play.input": "Input",
    "play.anonymized": "De-identified",
    "play.legend":
      "Colours follow the label, from your text to the tokens and back.",
    "play.edit": "Edit",
    "play.dropped": "Dropped",
    "play.lostTo": "lost to",
    "play.elapsed": "ms",
    "play.truncated": "Text cut to the playground limit.",
    "play.unsupported": "Not run here, needs a model:",
    "play.empty": "Run to see detections.",
    "play.nothing": "No detection.",
    "play.privacy":
      "Your text is not written to any database. It is de-identified to answer this request, then forgotten.",

    "compare.add": "Add",
    "compare.remove": "Remove",
    "compare.agreed": "Caught by all",
    "compare.disputed": "Caught by",
    "compare.noDispute": "Every object caught the same values.",
    "compare.go": "Compare",

    "chat.lede":
      "Your message is de-identified before the assistant sees it; the reply is restored before you read it. The assistant is scripted, so the demo is free and reproducible.",
    "chat.send": "Send",
    "chat.placeholder": "A message with an email or a phone number",
    "chat.reveal": "Show what the model sees",
    "chat.reset": "Reset",
    "chat.mapping": "Tokens",
    "chat.empty": "Send a message to start.",

    "draft.form": "Form",
    "draft.toml": "TOML",
    "draft.information": "Information",
    "draft.name": "Name",
    "draft.label": "Label",
    "draft.tags": "Tags",
    "draft.tagFilter": "Filter the vocabulary",
    "draft.tagRemove": "Remove this tag",
    "draft.regex": "Regex",
    "draft.regexNote":
      "Python re, compiled with re.ASCII. Avoid the single quote: it closes the TOML literal string the manifest writes it in.",
    "draft.description": "Description",
    "draft.examples": "Examples",
    "draft.matches": "Must be caught",
    "draft.matchText": "A sentence",
    "draft.matchValue": "The value in it",
    "draft.noMatches": "Must be left alone",
    "draft.add": "Add a row",
    "draft.remove": "Remove",
    "draft.redos": "Backtracking recipe",
    "draft.redosNote":
      "A valid prefix, an ambiguous fragment repeated to 100,000 characters, then an ending that forbids the match. This is what bounds the regex against a hostile text.",
    "draft.prefix": "Prefix",
    "draft.filler": "Filler",
    "draft.suffix": "Suffix",
    "draft.ok": "Caught as expected",
    "draft.nothing": "nothing caught",
    "draft.sources": "Sources",
    "draft.source": "Source",
    "draft.sourcesNote":
      "In order. On two identical spans the first source declared wins, so moving a row changes which label a value comes out under.",
    "draft.addSource": "Add a source",
    "draft.exclude": "Leave out of this source",
    "draft.moveUp": "Move up",
    "draft.moveDown": "Move down",
    "draft.name.kebab": "The name is lower case words joined by dashes.",
    "draft.label.snake": "The label is upper case words joined by underscores.",
    "draft.tags.empty": "Pick at least one tag.",
    "draft.regex.empty": "Write the regex.",
    "draft.regex.quote":
      "The regex holds a single quote, which the manifest cannot carry.",
    "draft.description.empty": "A description is required.",
    "draft.descriptionNote":
      "In English, the language every manifest is written in. A French translation can be added in the pull request.",
    "draft.description.dash":
      "Replace the em-dash with a comma or a full stop.",
    "draft.matches.two": "Two sentences that must be caught are required.",
    "draft.match.incomplete":
      "A row needs both a sentence and the value inside it.",
    "draft.match.once": "The value has to appear exactly once in its sentence.",
    "draft.noMatches.two":
      "Two sentences that must be left alone are required.",
    "draft.redos.incomplete": "The filler and the suffix are required.",
    "draft.sources.one": "A group needs at least one source.",
    "draft.sources.twice": "The same source is listed twice.",
    "try.title": "Try it",
    "try.go": "Run here",
    "try.loading": "Loading the engine",
    "try.text": "A text to try the group on",
    "try.note": "piighost runs in this tab. Your text stays on your machine.",
    "contribute.lede":
      "Propose a pattern or a group of patterns. Checked here, merged by pull request.",
    "contribute.what": "What are you proposing?",
    "contribute.pattern.note": "One shape and the label it emits.",
    "contribute.group.note": "A reusable set of patterns.",
    "contribute.kind": "Kind",
    "contribute.namespace": "Namespace",
    "contribute.name": "Name",
    "contribute.base": "Base object",
    "contribute.fork": "Start from this one",
    "contribute.fork.draft":
      "Fills the form with it, examples included. Change the shape and keep the cases it already gets right.",
    "contribute.create": "Create",
    "contribute.path": "Path",
    "contribute.ok": "Every check passed.",
    "contribute.openPr": "Open the pull request",
    "contribute.findings": "Findings",

    "stats.title": "Usage",
    "stats.lede": "What the catalog is asked for, counted rather than logged.",
    "stats.window": "Window",
    "stats.7": "7 days",
    "stats.30": "30 days",
    "stats.90": "90 days",
    "stats.perDay": "Pulls per day",
    "stats.top": "Most pulled",
    "stats.selectors": "Pinned or floating",
    "stats.selectorsNote":
      "A commit is pinned and reproducible. A tag follows what its owner moves. The bare name follows the head.",
    "stats.clients": "Who is asking",
    "stats.privacy":
      "These are counters, not a log. The finest resolution is the hour, a row is a shape rather than a request, and no address, browser identity or text is recorded anywhere.",

    "labels.title": "Labels",
    "configs.title": "piighost configs",
    "home.configsNote":
      "Patterns and groups. The pipelines built from them are the",
    "configs.lede":
      "Pipelines assembled from the catalog's groups: a detector, then what happens once something is found. The catalog itself is the regexes.",
    "configs.link": "piighost configs",
    "labels.lede":
      "Every label this catalog can emit, and the pattern that defines it.",
    "labels.definedBy": "defined by",

    "common.loading": "Loading",
    "common.error": "Something went wrong",
    "common.retry": "Retry",
    "common.notFound": "Nothing here",
    "common.notFoundLede": "That page does not exist.",
    "common.back": "Back to the catalog",
    "common.close": "Close",
    "common.copy": "Copy",
    "common.copied": "Copied",
    "common.copyFailed": "Copy failed",
    "common.colon": ":",
    "common.unreachable": "the request did not reach the server",
    "common.level.error": "error",
    "common.level.warning": "warning",
    "common.level.info": "info",

    "footer.tagline":
      "Tested, versioned de-identification regexes for piighost.",
    "footer.links": "Links",
    "footer.docs": "Documentation",
    "footer.chat": "Ask the documentation",
    "footer.mit": "MIT license.",
  },
  fr: {
    "nav.catalogue": "Catalogue",
    "nav.playground": "Bac à sable",
    "nav.contribute": "Contribuer",
    "nav.github": "GitHub",
    "nav.theme": "Changer de thème",
    "nav.language": "Changer de langue",
    "nav.skip": "Aller au contenu",
    "nav.menu": "Menu",
    "nav.main": "Navigation principale",

    "home.title": "piighost catalog",
    "home.lede":
      "Explorez et proposez des regex de dé-identification testés\u00a0: des motifs seuls, et les groupes qui les composent.",
    "home.search": "Chercher un motif, un groupe, un label, un tag...",
    "home.all": "Tout",
    "home.patterns": "Motifs",
    "home.groups": "Groupes",
    "home.configs": "Configurations",
    "home.empty": "Rien ne correspond à ces filtres.",
    "home.clear": "Effacer",
    "home.usedBy": "utilisé par",
    "home.tryIt": "Essayer",
    "home.playground":
      "Un texte à vérifier\u00a0? Passez-le à n'importe quel motif dans le",
    "home.updated": "Mis à jour",
    "home.never": "non enregistré",
    "home.sort": "Trier",
    "home.sort.relevance": "Pertinence",
    "home.sort.updated": "Mis à jour récemment",
    "home.sort.used": "Les plus utilisés",
    "home.sort.labels": "Couverture la plus large",
    "home.sort.pulls": "Les plus récupérés",
    "home.sort.name": "Nom",
    "home.page": "Page",
    "home.previous": "Précédent",
    "home.next": "Suivant",
    "facet.type": "Type",
    "facet.more": "Voir plus",
    "facet.less": "Voir moins",
    "facet.region": "Région",
    "facet.category": "Catégorie",
    "facet.domain": "Métier",
    "facet.use-case": "Cas d'usage",
    "facet.language": "Langue",
    "detail.content": "Contenu",
    "detail.history": "Historique des commits",
    "detail.copyRef": "Copier la référence",
    "detail.tryIt": "Essayer",
    "detail.unrecorded": "tête non enregistrée",

    "kind.pattern": "motif",
    "kind.group": "groupe",
    "kind.config": "config piighost",

    "pick.filter": "Filtrer par nom, label ou tag",
    "pick.none": "Aucun résultat.",

    "detail.openPlayground": "Ouvrir dans le bac à sable",
    "detail.download": "Télécharger le TOML",
    "detail.pipeline": "Fichier de pipeline",
    "detail.flattened": "Inliné",
    "detail.referenced": "Par id du catalogue",
    "detail.pullsWindow": "Sur les trente derniers jours",
    "detail.memory": "Mémoire",
    "detail.part": "Portée",
    "detail.wholePipeline": "Pipeline complet",
    "detail.detectorOnly": "Détecteur seul",
    "detail.detectorNote":
      "Le détecteur seul, à coller dans un pipeline que vous avez déjà. Le linker, l'anonymiseur et la mémoire restent les vôtres.",
    "detail.none": "aucune",
    "detail.use": "L'utiliser",
    "detail.commits": "Commits",
    "detail.pattern": "Motif",
    "detail.engine": "Python re, ASCII",
    "detail.matches": "Doit reconnaître",
    "detail.noMatches": "Ne doit pas reconnaître",
    "detail.sources": "Sources",
    "detail.sourcesNote":
      "Ordre d'insertion. Sur un span identique, la première source l'emporte.",
    "detail.labels": "Labels",
    "detail.detectors": "Détecteurs",
    "detail.from": "vient de",
    "detail.excluded": "exclu",
    "detail.only": "seulement",

    "play.run": "Lancer",
    "play.compare": "Comparer",
    "play.chat": "Chat",
    "play.configure": "Configurer",
    "play.text": "Texte",
    "play.results": "Résultats",
    "play.object": "Objet",
    "play.candidate": "Regex",
    "play.candidateNote":
      "Hors catalogue. Tourne dans un processus séparé, tué au bout de deux secondes.",
    "play.regexPlaceholder": "Un regex à essayer",
    "play.sample": "Charger un exemple",
    "play.go": "Lancer",
    "play.running": "En cours",
    "play.input": "Saisie",
    "play.anonymized": "Dé-identifié",
    "play.legend":
      "Les couleurs suivent le label, de votre texte aux jetons et retour.",
    "play.edit": "Modifier",
    "play.dropped": "Écartées",
    "play.lostTo": "au profit de",
    "play.elapsed": "ms",
    "play.truncated": "Texte coupé à la limite du bac à sable.",
    "play.unsupported": "Non exécuté ici, demande un modèle\u00a0:",
    "play.empty": "Lancez pour voir les détections.",
    "play.nothing": "Aucune détection.",
    "play.privacy":
      "Votre texte n'est enregistré dans aucune base. Il est dé-identifié pour répondre à cette requête, puis oublié.",

    "compare.add": "Ajouter",
    "compare.remove": "Retirer",
    "compare.agreed": "Reconnu par tous",
    "compare.disputed": "Repéré par",
    "compare.noDispute": "Tous les objets ont repéré les mêmes valeurs.",
    "compare.go": "Comparer",

    "chat.lede":
      "Votre message est dé-identifié avant que l'assistant le voie\u00a0; la réponse est restaurée avant que vous la lisiez. L'assistant est scripté, donc la démo est gratuite et reproductible.",
    "chat.send": "Envoyer",
    "chat.placeholder": "Un message avec un e-mail ou un téléphone",
    "chat.reveal": "Voir ce que le modèle voit",
    "chat.reset": "Recommencer",
    "chat.mapping": "Jetons",
    "chat.empty": "Envoyez un message pour commencer.",

    "draft.form": "Formulaire",
    "draft.toml": "TOML",
    "draft.information": "Informations",
    "draft.name": "Nom",
    "draft.label": "Label",
    "draft.tags": "Tags",
    "draft.tagFilter": "Filtrer le vocabulaire",
    "draft.tagRemove": "Retirer ce tag",
    "draft.regex": "Regex",
    "draft.regexNote":
      "Python re, compilé avec re.ASCII. Évitez l'apostrophe droite\u00a0: elle ferme la chaîne littérale TOML dans laquelle le manifeste l'écrit.",
    "draft.description": "Description",
    "draft.examples": "Exemples",
    "draft.matches": "Doit être reconnu",
    "draft.matchText": "Une phrase",
    "draft.matchValue": "La valeur qu'elle contient",
    "draft.noMatches": "Ne doit rien reconnaître",
    "draft.add": "Ajouter une ligne",
    "draft.remove": "Retirer",
    "draft.redos": "Recette de backtracking",
    "draft.redosNote":
      "Un préfixe valide, un fragment ambigu répété jusqu'à 100 000 caractères, puis une fin qui interdit la correspondance. C'est ce qui borne le regex face à un texte hostile.",
    "draft.prefix": "Préfixe",
    "draft.filler": "Remplissage",
    "draft.suffix": "Fin",
    "draft.ok": "Reconnu comme prévu",
    "draft.nothing": "rien reconnu",
    "draft.sources": "Sources",
    "draft.source": "Source",
    "draft.sourcesNote":
      "Dans l'ordre. Sur deux spans identiques, la première source déclarée gagne, donc déplacer une ligne change le label sous lequel une valeur ressort.",
    "draft.addSource": "Ajouter une source",
    "draft.exclude": "Écarter de cette source",
    "draft.moveUp": "Monter",
    "draft.moveDown": "Descendre",
    "draft.name.kebab":
      "Le nom s'écrit en minuscules, les mots reliés par des tirets.",
    "draft.label.snake":
      "Le label s'écrit en majuscules, les mots reliés par des tirets bas.",
    "draft.tags.empty": "Choisissez au moins un tag.",
    "draft.regex.empty": "Écrivez le regex.",
    "draft.regex.quote":
      "Le regex contient une apostrophe droite, que le manifeste ne peut pas porter.",
    "draft.description.empty": "Une description est obligatoire.",
    "draft.descriptionNote":
      "En anglais, la langue de tous les manifestes. Une traduction française peut s'ajouter dans la pull request.",
    "draft.description.dash":
      "Remplacez le tiret cadratin par une virgule ou un point.",
    "draft.matches.two":
      "Deux phrases qui doivent être reconnues sont nécessaires.",
    "draft.match.incomplete":
      "Une ligne demande une phrase et la valeur qu'elle contient.",
    "draft.match.once":
      "La valeur doit apparaître exactement une fois dans sa phrase.",
    "draft.noMatches.two":
      "Deux phrases qui ne doivent rien déclencher sont nécessaires.",
    "draft.redos.incomplete": "Le remplissage et la fin sont obligatoires.",
    "draft.sources.one": "Un groupe demande au moins une source.",
    "draft.sources.twice": "La même source est listée deux fois.",
    "try.title": "Essayer",
    "try.go": "Lancer ici",
    "try.loading": "Chargement du moteur",
    "try.text": "Un texte pour essayer le groupe",
    "try.note": "piighost tourne dans cet onglet. Votre texte reste chez vous.",
    "contribute.lede":
      "Proposez un motif ou un groupe de motifs. Vérifié ici, fusionné par pull request.",
    "contribute.what": "Que proposez-vous\u00a0?",
    "contribute.pattern.note": "Un motif et le label qu'il produit.",
    "contribute.group.note": "Un ensemble de motifs réutilisable.",
    "contribute.kind": "Type",
    "contribute.namespace": "Espace de noms",
    "contribute.name": "Nom",
    "contribute.base": "Objet de base",
    "contribute.fork": "Partir de celui-ci",
    "contribute.fork.draft":
      "Remplit le formulaire avec lui, exemples compris. Changez la forme et gardez les cas qu'il reconnaît déjà.",
    "contribute.create": "Créer",
    "contribute.path": "Chemin",
    "contribute.ok": "Tous les contrôles passent.",
    "contribute.openPr": "Ouvrir la pull request",
    "contribute.findings": "Constats",

    "stats.title": "Usage",
    "stats.lede": "Ce qu'on demande au catalogue, compté et non journalisé.",
    "stats.window": "Fenêtre",
    "stats.7": "7 jours",
    "stats.30": "30 jours",
    "stats.90": "90 jours",
    "stats.perDay": "Récupérations par jour",
    "stats.top": "Les plus récupérés",
    "stats.selectors": "Épinglé ou flottant",
    "stats.selectorsNote":
      "Un commit est épinglé et reproductible. Un tag suit ce que son propriétaire déplace. Le nom nu suit la tête.",
    "stats.clients": "Qui demande",
    "stats.privacy":
      "Ce sont des compteurs, pas un journal. La résolution la plus fine est l'heure, une ligne est une forme et non une requête, et aucune adresse, aucune identité de navigateur, aucun texte n'est enregistré nulle part.",

    "labels.title": "Labels",
    "configs.title": "Configs piighost",
    "home.configsNote":
      "Motifs et groupes. Les pipelines qui en sont faits sont les",
    "configs.lede":
      "Des pipelines assemblés à partir des groupes du catalogue\u00a0: un détecteur, puis ce qui se passe une fois quelque chose trouvé. Le catalogue lui-même, ce sont les regex.",
    "configs.link": "Configs piighost",
    "labels.lede":
      "Tous les labels que ce catalogue peut émettre, et le motif qui les définit.",
    "labels.definedBy": "défini par",

    "common.loading": "Chargement",
    "common.error": "Quelque chose a échoué",
    "common.retry": "Réessayer",
    "common.notFound": "Rien ici",
    "common.notFoundLede": "Cette page n'existe pas.",
    "common.back": "Retour au catalogue",
    "common.close": "Fermer",
    "common.copy": "Copier",
    "common.copied": "Copié",
    "common.copyFailed": "Copie impossible",
    "common.colon": "\u00a0:",
    "common.unreachable": "la requête n'a pas atteint le serveur",
    "common.level.error": "erreur",
    "common.level.warning": "avertissement",
    "common.level.info": "info",

    "footer.tagline":
      "Des regex de dé-identification testés et versionnés pour piighost.",
    "footer.links": "Liens",
    "footer.docs": "Documentation",
    "footer.chat": "Interroger la documentation",
    "footer.mit": "Licence MIT.",
  },
} as const;

export type Key = keyof (typeof STRINGS)["en"];

/**
 * The words that follow a count, by plural category.
 *
 * Intl.PluralRules gives the category, so "1 result" and "2 results" in
 * English, and "0 résultat", "1 résultat", "2 résultats" in French, where zero
 * takes the singular. French also has a `many` category for round millions,
 * which falls back to `other`.
 */
const PLURALS = {
  en: {
    results: { one: "result", other: "results" },
    labels: { one: "label", other: "labels" },
    uses: { one: "use", other: "uses" },
    pulls: { one: "pull", other: "pulls" },
    kept: { one: "kept", other: "kept" },
    caught: { one: "caught", other: "caught" },
    coverage: { one: "label covered", other: "labels covered" },
    pipelinesPulled: { one: "pipeline pulled", other: "pipelines pulled" },
    objectsBrowsed: { one: "object looked at", other: "objects looked at" },
    searches: { one: "search", other: "searches" },
  },
  fr: {
    results: { one: "résultat", other: "résultats" },
    labels: { one: "label", other: "labels" },
    uses: { one: "usage", other: "usages" },
    pulls: { one: "récupération", other: "récupérations" },
    kept: { one: "gardée", other: "gardées" },
    caught: { one: "reconnue", other: "reconnues" },
    coverage: { one: "label couvert", other: "labels couverts" },
    pipelinesPulled: { one: "pipeline récupéré", other: "pipelines récupérés" },
    objectsBrowsed: { one: "objet consulté", other: "objets consultés" },
    searches: { one: "recherche", other: "recherches" },
  },
} as const;

export type PluralKey = keyof (typeof PLURALS)["en"];

/** A text from the catalog, in English and optionally in French. */
export type Localized = { en: string; fr?: string | null } | null | undefined;

export const LOCALES: Locale[] = ["en", "fr"];

/** The language a browser asks for: French if it says so first, else English. */
export function preferredLocale(): Locale {
  const asked = typeof navigator === "undefined" ? "" : navigator.language;
  return asked.toLowerCase().startsWith("fr") ? "fr" : "en";
}

/**
 * The French typographic spaces, for a text the dictionary does not hold.
 *
 * The manifests write `Paneuropéen : IBAN` with a plain space, which a line
 * break can split from its colon. A no-break space before : ; ? ! and inside
 * guillemets keeps them together, the rule the dictionary follows by hand.
 */
export function frenchSpacing(text: string): string {
  return text.replace(/ ([:;?!»])/g, "\u00a0$1").replace(/« /g, "«\u00a0");
}

class I18n {
  /** Set by the router from the path prefix, never by hand. */
  locale = $state<Locale>("en");

  t(key: Key): string {
    const table = STRINGS[this.locale] as Record<string, string>;
    return table[key] ?? STRINGS.en[key] ?? key;
  }

  /** The word for `count` things, without the count itself. */
  plural(key: PluralKey, count: number): string {
    const forms = PLURALS[this.locale][key] as Record<string, string>;
    const category = new Intl.PluralRules(this.locale).select(count);
    return forms[category] ?? forms.other;
  }

  /**
   * A text from the catalog in the page's language, and the language it is
   * really in: French is optional in a manifest, so a French page shows the
   * English text where there is none, and says so with `lang`.
   */
  localized(text: Localized): { text: string; lang: Locale } {
    const french = text?.fr;
    if (this.locale === "fr" && french) return { text: french, lang: "fr" };
    return { text: text?.en ?? "", lang: "en" };
  }

  /** The text alone, for an attribute or an option. */
  pick(text: Localized): string {
    const { text: value, lang } = this.localized(text);
    return lang === "fr" ? frenchSpacing(value) : value;
  }
}

export const i18n = new I18n();
export const t = (key: Key) => i18n.t(key);
export const plural = (key: PluralKey, count: number) =>
  i18n.plural(key, count);
