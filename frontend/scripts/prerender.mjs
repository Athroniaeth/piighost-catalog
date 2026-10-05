/**
 * Write one HTML file per route, so a crawler that does not run JavaScript
 * still reads the registry.
 *
 * The site is a single page application: every URL served the same 1.3 KB of
 * empty document, with `piighost catalog` as its title and nothing in its body.
 * Google renders JavaScript, eventually and within a budget; the crawlers that
 * feed the assistants people now ask "how do I redact PII before a prompt"
 * mostly do not. Two hundred and twenty-six pages of real content were
 * invisible to them.
 *
 * This runs after `vite build` and rewrites `dist/<route>/index.html` from the
 * built document, so the hashed asset URLs stay right. The head gets a real
 * title, description, canonical and JSON-LD; `#app` gets the same content the
 * application renders, in plain HTML. The bundle then replaces it on mount, so
 * a visitor and a crawler are served the same page — no cloaking, and the
 * prerendered copy is what shows while the bundle loads.
 *
 * Reads the manifests straight from `registry/`, not from the API: a build must
 * not need a running server, and the registry is already in the build context.
 *
 * The pages also link to each other. The first version of this script wrote 226
 * correct documents with no anchors between them, reachable only from the
 * sitemap: a crawler that landed on one found nothing to follow and left. Every
 * page now carries the navigation, the catalog lists every object, and an
 * object page names the groups that use it, its neighbours by tag, and the
 * object before and after it in the index — so the whole registry is walkable
 * from any entry point, which is what a crawler and a reader both need.
 *
 * Every page is written twice, under /en/ and /fr/, the scheme every piighost
 * site links to, each with its `lang`, its canonical URL and the hreflang
 * alternates that tie the two together. The French page carries the French
 * description where a manifest has one, and the English one, marked
 * `lang="en"`, where it has not. `dist/index.html` is left as Vite wrote it: it
 * is the shell nginx falls back to, and it belongs to no page.
 */

import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "smol-toml";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const REGISTRY = join(ROOT, "registry");
const DIST = resolve(HERE, "..", "dist");
const ORIGIN =
  process.env.SITE_URL?.replace(/\/$/, "") || "https://catalog.piighost.dev";

const LOCALES = ["en", "fr"];

/** The words of the prerendered pages, in both languages. */
const COPY = {
  en: {
    nav: "Catalog",
    routes: {
      "/": "Catalog",
      "/labels": "Labels",
      "/configs": "Configs",
      "/playground": "Playground",
      "/contribute": "Contribute",
    },
    kind: { pattern: "pattern", group: "group", config: "piighost config" },
    kinds: { pattern: "patterns", group: "groups", config: "piighost configs" },
    label: "Label",
    tags: "Tags",
    pattern: "Pattern",
    sources: "Sources",
    caught: "Must be caught",
    leftAlone: "Must be left alone",
    download: "Download the detector as TOML",
    usedBy: "Used by",
    related: "Related patterns",
    all: (kinds) => `All ${kinds} in the catalog`,
    patterns: "Patterns",
    groups: "Groups",
    configs: "piighost configs",
    noConfig:
      "No configuration is published yet. The catalog holds patterns and groups.",
    compare:
      '<a href="/en/playground/compare">Compare several objects on the same ' +
      "text</a>, value by value.",
    stats:
      '<a href="/en/stats">What the catalog is asked for</a>: pulls, searches ' +
      "and the objects behind them.",
    fallback: (key) => `The ${key} de-identification pattern.`,
  },
  fr: {
    nav: "Catalogue",
    routes: {
      "/": "Catalogue",
      "/labels": "Labels",
      "/configs": "Configs",
      "/playground": "Bac à sable",
      "/contribute": "Contribuer",
    },
    kind: { pattern: "motif", group: "groupe", config: "config piighost" },
    kinds: { pattern: "motifs", group: "groupes", config: "configs piighost" },
    label: "Label",
    tags: "Tags",
    pattern: "Motif",
    sources: "Sources",
    caught: "Doit être reconnu",
    leftAlone: "Ne doit rien reconnaître",
    download: "Télécharger le détecteur en TOML",
    usedBy: "Utilisé par",
    related: "Motifs voisins",
    all: (kinds) => `Tous les ${kinds} du catalogue`,
    patterns: "Motifs",
    groups: "Groupes",
    configs: "Configs piighost",
    noConfig:
      "Aucune configuration n'est encore publiée. Le catalogue contient des motifs et des groupes.",
    compare:
      '<a href="/fr/playground/compare">Comparer plusieurs objets sur le même ' +
      "texte</a>, valeur par valeur.",
    stats:
      '<a href="/fr/stats">Ce qu\'on demande au catalogue</a>\u00a0: ' +
      "récupérations, recherches et les objets derrière elles.",
    fallback: (key) => `Le motif de dé-identification ${key}.`,
  },
};

/**
 * The French typographic spaces, as the site's lib/i18n.svelte.ts sets them: a
 * no-break space before : ; ? ! and inside guillemets.
 */
function frenchSpacing(text) {
  return text.replace(/ ([:;?!»])/g, "\u00a0$1").replace(/« /g, "«\u00a0");
}

/** A description in a language, and the language it is really in. */
function localized(text, lang) {
  if (lang === "fr" && text.fr) return { text: text.fr, lang: "fr" };
  return { text: text.en ?? "", lang: "en" };
}

/**
 * Escaped markup for a description: a pair of Markdown backticks becomes a code
 * span, as the site renders it, and French gets its no-break spaces.
 */
function prose(text, lang) {
  const pieces = String(text).split("`");
  if (pieces.length % 2 === 0) {
    const last = pieces.pop();
    pieces[pieces.length - 1] += "`" + last;
  }
  return pieces
    .map((piece, index) =>
      index % 2 === 1
        ? `<code>${esc(piece)}</code>`
        : esc(lang === "fr" ? frenchSpacing(piece) : piece),
    )
    .join("");
}

/** A description as a paragraph, `lang` set where it falls back to English. */
function paragraph(object, lang, limit = null) {
  const shown = localized(object.description, lang);
  const text = limit ? summary(shown.text, limit) : shown.text;
  const attr = shown.lang === lang ? "" : ` lang="${shown.lang}"`;
  return { html: prose(text, shown.lang), attr, plain: shown.text };
}

/** Text for a meta tag: no markup, so the backticks simply go. */
function plain(text, lang) {
  const bare = String(text).replaceAll("`", "");
  return lang === "fr" ? frenchSpacing(bare) : bare;
}

const KINDS = {
  patterns: { file: "pattern.toml", key: "pattern", kind: "pattern" },
  groups: { file: "group.toml", key: "group", kind: "group" },
  configs: { file: "config.toml", key: "config", kind: "config" },
};

/** Escape the five characters that change the meaning of markup. */
function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/** Every object in the registry, as {key, kind, name, description, content}. */
function readRegistry() {
  const objects = [];
  for (const [directory, spec] of Object.entries(KINDS)) {
    const root = join(REGISTRY, directory);
    if (!existsSync(root)) continue;
    for (const namespace of readdirSync(root)) {
      for (const name of readdirSync(join(root, namespace))) {
        const path = join(root, namespace, name, spec.file);
        if (!existsSync(path)) continue;
        const data = parse(readFileSync(path, "utf8"));
        const body = data[spec.key] ?? {};
        objects.push({
          key: `${namespace}/${name}`,
          kind: spec.kind,
          name,
          tags: body.tags ?? [],
          label: body.label ?? null,
          regex: body.regex ?? null,
          description: body.description ?? { en: "" },
          sources: (data.sources ?? []).map((s) => s.ref).filter(Boolean),
          examples: data.examples ?? {},
        });
      }
    }
  }
  return objects.sort((a, b) => a.key.localeCompare(b.key));
}

/** The path of a route under a language, the home with its slash. */
function under(lang, route) {
  return `/${lang}${route}`;
}

/**
 * The navigation, with the current page left as text rather than a self-link,
 * then the same page in the other language, the way the header's menu has it.
 */
function nav(current, lang, route) {
  const items = Object.entries(COPY[lang].routes)
    .map(([path, label]) =>
      path === current
        ? `<li>${esc(label)}</li>`
        : `<li><a href="${esc(under(lang, path))}">${esc(label)}</a></li>`,
    )
    .join("");
  const other = lang === "fr" ? "en" : "fr";
  const name = other === "fr" ? "Français" : "English";
  const switcher =
    `<li><a href="${esc(under(other, route))}" hreflang="${other}" ` +
    `lang="${other}">${name}</a></li>`;
  return `<nav aria-label="${esc(COPY[lang].nav)}"><ul>${items}${switcher}</ul></nav>`;
}

/** A list of objects as links, each followed by the sentence that names it. */
function objectList(objects, lang) {
  const items = objects
    .map((object) => {
      const text = paragraph(object, lang, 120);
      return (
        `<li><a href="${esc(under(lang, `/r/${object.key}`))}">${esc(object.key)}</a>` +
        (text.plain
          ? `${lang === "fr" ? "\u00a0:" : ":"} <span${text.attr}>${text.html}</span>`
          : "") +
        `</li>`
      );
    })
    .join("\n        ");
  return `<ul>\n        ${items}\n      </ul>`;
}

/** The first sentence, which is where a description says what it is. */
function summary(text, limit = 155) {
  const first = String(text).trim().split(". ")[0].trim();
  const clipped =
    first.length > limit
      ? `${first.slice(0, limit - 1).replace(/\s+\S*$/, "")}…`
      : first;
  return clipped + (clipped.endsWith("…") || clipped.endsWith(".") ? "" : ".");
}

/**
 * The readable body of an object page, which the bundle replaces on mount.
 *
 * `neighbours` is what turns the page from a leaf into a node: the groups that
 * use this object, the objects that share a tag with it, and the two objects
 * either side of it in the catalog. The last pair matters most — it chains
 * all 226 pages together, so a crawler that finds one finds the rest without
 * ever going back to the sitemap.
 */
function objectBody(object, neighbours, lang) {
  const copy = COPY[lang];
  const colon = lang === "fr" ? "\u00a0:" : ":";
  const text = paragraph(object, lang);
  const parts = [
    nav(null, lang, `/r/${object.key}`),
    `<h1>${esc(object.key)}</h1>`,
    `<p${text.attr}>${text.html}</p>`,
  ];
  if (object.label)
    parts.push(
      `<p>${copy.label}${colon} <code>${esc(object.label)}</code></p>`,
    );
  if (object.regex)
    parts.push(
      `<h2>${copy.pattern}</h2><pre><code>${esc(object.regex)}</code></pre>`,
    );
  if (object.sources.length) {
    const items = object.sources
      .map(
        (ref) =>
          `<li><a href="${esc(under(lang, `/r/${ref.split(":")[0]}`))}">${esc(ref)}</a></li>`,
      )
      .join("");
    parts.push(`<h2>${copy.sources}</h2><ul>${items}</ul>`);
  }
  const matches = object.examples.match ?? [];
  if (matches.length) {
    const items = matches
      .map(
        (e) =>
          `<li><code>${esc(e.text)}</code> → <code>${esc(e.value)}</code></li>`,
      )
      .join("");
    parts.push(`<h2>${copy.caught}</h2><ul>${items}</ul>`);
  }
  const noMatches = object.examples.no_match ?? [];
  if (noMatches.length) {
    const items = noMatches
      .map((e) => `<li><code>${esc(e.text)}</code></li>`)
      .join("");
    parts.push(`<h2>${copy.leftAlone}</h2><ul>${items}</ul>`);
  }
  if (object.tags.length) {
    parts.push(
      `<p>${copy.tags}${colon} ${object.tags.map((t) => esc(t)).join(", ")}</p>`,
    );
  }
  // The API is disallowed in robots.txt, so the link is for the reader; saying
  // so keeps it out of a crawler's queue instead of leaving it to be fetched
  // and refused.
  parts.push(
    `<p><a rel="nofollow" href="/api/v1/refs/${esc(object.key)}/latest/pipeline.toml?part=detector">` +
      `${copy.download}</a></p>`,
  );
  const { usedBy, related, previous, next } = neighbours;
  if (usedBy.length) {
    parts.push(`<h2>${copy.usedBy}</h2>${objectList(usedBy, lang)}`);
  }
  if (related.length) {
    parts.push(`<h2>${copy.related}</h2>${objectList(related, lang)}`);
  }
  const around = [
    previous
      ? `<a rel="prev" href="${esc(under(lang, `/r/${previous.key}`))}">← ${esc(previous.key)}</a>`
      : null,
    `<a href="${under(lang, "/")}">${esc(copy.all(copy.kinds[object.kind]))}</a>`,
    next
      ? `<a rel="next" href="${esc(under(lang, `/r/${next.key}`))}">${esc(next.key)} →</a>`
      : null,
  ].filter(Boolean);
  parts.push(`<nav aria-label="${esc(copy.nav)}">${around.join(" · ")}</nav>`);
  return parts.join("\n      ");
}

/**
 * What an object page links to besides itself.
 *
 * `related` is capped: a tag like `fr` covers thirty objects, and a page that
 * links to all of them dilutes the ones that matter. Six is enough to give a
 * crawler somewhere to go and a reader something to read, and the previous and
 * next links guarantee the rest is reachable anyway.
 */
function neighboursOf(object, objects, index) {
  const usedBy = objects.filter((other) =>
    other.sources.some((ref) => ref.split(":")[0] === object.key),
  );
  const linked = new Set([
    object.key,
    ...usedBy.map((o) => o.key),
    ...object.sources.map((ref) => ref.split(":")[0]),
  ]);
  const tags = new Set(object.tags);
  const related = objects
    .filter(
      (other) =>
        !linked.has(other.key) &&
        other.kind === object.kind &&
        other.tags.some((tag) => tags.has(tag)),
    )
    .slice(0, 6);
  return {
    usedBy,
    related,
    previous: objects[index - 1] ?? null,
    next: objects[index + 1] ?? null,
  };
}

/**
 * schema.org for an object.
 *
 * A registry entry is a Dataset, and the registry a DataCatalog. That is not a
 * stretch to please a crawler: each object is a versioned, addressable set of
 * records with a licence and a provenance, which is what the vocabulary means.
 * It also puts the catalog in Google Dataset Search, where nothing in this field
 * currently is.
 */
function objectJsonLd(object, lang) {
  const shown = localized(object.description, lang);
  return {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: object.key,
    inLanguage: shown.lang,
    description:
      plain(shown.text, shown.lang) || COPY[lang].fallback(object.key),
    url: `${ORIGIN}${under(lang, `/r/${object.key}`)}`,
    identifier: object.key,
    keywords: [
      ...object.tags,
      "PII",
      "de-identification",
      "regex",
      "pseudonymization",
    ],
    license: "https://opensource.org/licenses/MIT",
    isPartOf: {
      "@type": "DataCatalog",
      name: "piighost catalog",
      url: `${ORIGIN}${under(lang, "/")}`,
    },
    distribution: {
      "@type": "DataDownload",
      encodingFormat: "text/toml",
      contentUrl: `${ORIGIN}/api/v1/refs/${object.key}/latest/pipeline.toml?part=detector`,
    },
  };
}

/** Replace the head metadata of the built document and fill `#app`. */
function render(template, { lang, route, title, description, jsonLd, body }) {
  const canonical = `${ORIGIN}${under(lang, route)}`;
  let html = template;
  html = html.replace(/<html lang="[^"]*">/, `<html lang="${lang}">`);
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`);
  html = html.replace(
    /<meta\s+name="description"\s+content="[^"]*"\s*\/?>/,
    `<meta name="description" content="${esc(description)}" />`,
  );
  html = html.replace(
    /<meta\s+property="og:title"\s+content="[^"]*"\s*\/?>/,
    `<meta property="og:title" content="${esc(title)}" />`,
  );
  html = html.replace(
    /<meta\s+property="og:description"\s+content="[^"]*"\s*\/?>/,
    `<meta property="og:description" content="${esc(description)}" />`,
  );
  // og:image in absolute form: link previews (Discord, Slack, X) ignore a
  // relative URL. A PNG, not the SVG it is drawn from: most of them do not
  // display SVG at all.
  html = html.replace(
    /<meta\s+property="og:image"\s+content="[^"]*"\s*\/?>/,
    `<meta property="og:image" content="${esc(ORIGIN)}/og.png" />`,
  );
  // One alternate per language, and x-default for a visitor whose language is
  // neither: English, as the redirect of an unprefixed URL gives a browser
  // that asks for no French.
  const alternates = [...LOCALES, "x-default"].map(
    (code) =>
      `<link rel="alternate" hreflang="${code}" href="${esc(
        `${ORIGIN}${under(code === "x-default" ? "en" : code, route)}`,
      )}" />`,
  );
  const head = [
    `<link rel="canonical" href="${esc(canonical)}" />`,
    ...alternates,
    `<meta property="og:url" content="${esc(canonical)}" />`,
    `<meta property="og:locale" content="${lang === "fr" ? "fr_FR" : "en_US"}" />`,
    `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>`,
  ].join("\n    ");
  html = html.replace("</head>", `  ${head}\n  </head>`);
  return html.replace(
    '<div id="app"></div>',
    `<div id="app">\n      ${body}\n    </div>`,
  );
}

function write(lang, route, html) {
  const directory = join(DIST, lang, route.replace(/^\//, ""));
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, "index.html"), html);
}

const template = readFileSync(join(DIST, "index.html"), "utf8");
const objects = readRegistry();
const counts = { pattern: 0, group: 0, config: 0 };
for (const object of objects) counts[object.kind] += 1;

for (const lang of LOCALES) {
  objects.forEach((object, index) => {
    const route = `/r/${object.key}`;
    const shown = localized(object.description, lang);
    write(
      lang,
      route,
      render(template, {
        lang,
        route,
        title: `${object.key} · ${COPY[lang].kind[object.kind]} · piighost catalog`,
        description: plain(summary(shown.text), shown.lang),
        jsonLd: objectJsonLd(object, lang),
        body: objectBody(object, neighboursOf(object, objects, index), lang),
      }),
    );
  });
}

/**
 * The bodies of the pages that are not an object.
 *
 * The catalog lists every object rather than a selection. It is the page a
 * crawler reaches first and the one that carries the most weight, so spending
 * it on a summary and sending the rest to the sitemap was the wrong trade: one
 * page of 226 links is how the registry gets crawled at all.
 */
function staticBody(route, heading, description, lang) {
  const copy = COPY[lang];
  const parts = [
    nav(route, lang, route),
    `<h1>${esc(heading)}</h1>`,
    `<p>${esc(description)}</p>`,
  ];
  const of = (kind) => objects.filter((object) => object.kind === kind);
  if (route === "/") {
    parts.push(`<h2>${copy.patterns}</h2>${objectList(of("pattern"), lang)}`);
    parts.push(`<h2>${copy.groups}</h2>${objectList(of("group"), lang)}`);
    const configs = of("config");
    if (configs.length)
      parts.push(`<h2>${copy.configs}</h2>${objectList(configs, lang)}`);
  } else if (route === "/labels") {
    // A label is what a detector emits, and several patterns can emit the same
    // one. Grouping by label is the question a reader actually arrives with:
    // "what catches an IBAN?", not "what is piighost/eu-iban?".
    const byLabel = new Map();
    for (const object of objects) {
      if (!object.label) continue;
      if (!byLabel.has(object.label)) byLabel.set(object.label, []);
      byLabel.get(object.label).push(object);
    }
    const sections = [...byLabel.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(
        ([label, carriers]) =>
          `<h2>${esc(label)}</h2>${objectList(carriers, lang)}`,
      );
    parts.push(sections.join("\n      "));
  } else if (route === "/configs") {
    const configs = of("config");
    parts.push(
      configs.length ? objectList(configs, lang) : `<p>${copy.noConfig}</p>`,
    );
  } else if (route === "/playground") {
    // Compare is a mode of the playground, not a sibling of it, so it is named
    // here rather than in the navigation. Without this it is in the sitemap
    // with nothing pointing at it, which is how a page gets crawled once and
    // then forgotten.
    parts.push(`<p>${copy.compare}</p>`);
  }
  if (route === "/") parts.push(`<p>${copy.stats}</p>`);
  return parts.join("\n      ");
}

/** The pages that are not an object, by language: title, description, heading. */
const STATIC = {
  en: [
    {
      route: "/",
      title: "piighost catalog · tested de-identification regexes",
      description:
        `A catalog of ${counts.pattern} tested de-identification regex patterns and ` +
        `${counts.group} groups for piighost, each carrying the cases it must catch and ` +
        `the cases it must leave alone.`,
      heading: "piighost catalog",
    },
    {
      route: "/labels",
      title: "Labels · piighost catalog",
      description:
        "Every label the catalog emits, and the patterns that define it, from EMAIL " +
        "and FR_SIRET to the credential shapes a traceback leaks.",
      heading: "Labels",
    },
    {
      route: "/configs",
      title: "piighost configs · piighost catalog",
      description:
        "Pipelines assembled from the catalog's groups: a detector, then what happens " +
        "once something is found.",
      heading: "piighost configs",
    },
    {
      route: "/playground",
      title: "Playground · run a de-identification pattern on your own text",
      description:
        "Run any catalog object over a text and see what it catches, what it drops " +
        "and why. Your text is never written to a database.",
      heading: "Playground",
    },
    {
      route: "/playground/compare",
      title: "Compare de-identification patterns · piighost catalog",
      description:
        "Run several catalog objects over the same text and see where they disagree, " +
        "value by value.",
      heading: "Compare",
    },
    {
      route: "/contribute",
      title: "Contribute a pattern · piighost catalog",
      description:
        "Propose a regex pattern or a group of patterns. Checked here with the " +
        "maintainers' own tests, merged by pull request.",
      heading: "Contribute",
    },
    {
      route: "/stats",
      title: "Usage · piighost catalog",
      description:
        "What the catalog is asked for: pulls, searches and the objects behind them.",
      heading: "Usage",
    },
  ],
  fr: [
    {
      route: "/",
      title: "piighost catalog · des regex de dé-identification testés",
      description:
        `Un catalogue de ${counts.pattern} motifs regex de dé-identification testés et ` +
        `${counts.group} groupes pour piighost, chacun avec les cas qu'il doit reconnaître ` +
        `et ceux qu'il doit laisser tranquilles.`,
      heading: "piighost catalog",
    },
    {
      route: "/labels",
      title: "Labels · piighost catalog",
      description:
        "Tous les labels que le catalogue émet, et les motifs qui les définissent, " +
        "d'EMAIL et FR_SIRET aux formes de secret qu'une traceback laisse fuir.",
      heading: "Labels",
    },
    {
      route: "/configs",
      title: "Configs piighost · piighost catalog",
      description:
        "Des pipelines assemblés à partir des groupes du catalogue\u00a0: un détecteur, " +
        "puis ce qui se passe une fois quelque chose trouvé.",
      heading: "Configs piighost",
    },
    {
      route: "/playground",
      title: "Bac à sable · un motif de dé-identification sur votre texte",
      description:
        "Passez n'importe quel objet du catalogue sur un texte et voyez ce qu'il " +
        "reconnaît, ce qu'il écarte et pourquoi. Votre texte n'est écrit dans aucune base.",
      heading: "Bac à sable",
    },
    {
      route: "/playground/compare",
      title: "Comparer des motifs de dé-identification · piighost catalog",
      description:
        "Passez plusieurs objets du catalogue sur le même texte et voyez où ils " +
        "divergent, valeur par valeur.",
      heading: "Comparer",
    },
    {
      route: "/contribute",
      title: "Proposer un motif · piighost catalog",
      description:
        "Proposez un motif regex ou un groupe de motifs. Vérifié ici avec les tests " +
        "des mainteneurs, fusionné par pull request.",
      heading: "Contribuer",
    },
    {
      route: "/stats",
      title: "Usage · piighost catalog",
      description:
        "Ce qu'on demande au catalogue\u00a0: récupérations, recherches et les objets " +
        "derrière elles.",
      heading: "Usage",
    },
  ],
};

function catalogJsonLd(lang) {
  return {
    "@context": "https://schema.org",
    "@type": "DataCatalog",
    name: "piighost catalog",
    url: `${ORIGIN}${under(lang, "/")}`,
    inLanguage: lang,
    description:
      lang === "fr"
        ? "Un catalogue de regex de dé-identification testés pour piighost\u00a0: des " +
          "motifs, et les groupes qui les composent."
        : "A catalog of tested de-identification regexes for piighost: patterns, and " +
          "the groups that compose them.",
    license: "https://opensource.org/licenses/MIT",
    keywords: [
      "PII",
      "de-identification",
      "pseudonymization",
      "regex",
      "LLM",
      "GDPR",
      "prompt privacy",
    ],
    provider: {
      "@type": "Organization",
      name: "piighost",
      url: "https://piighost.dev",
    },
    potentialAction: {
      "@type": "SearchAction",
      target: `${ORIGIN}${under(lang, "/")}?q={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  };
}

for (const lang of LOCALES) {
  for (const page of STATIC[lang]) {
    write(
      lang,
      page.route,
      render(template, {
        lang,
        route: page.route,
        title: page.title,
        description: page.description,
        jsonLd: catalogJsonLd(lang),
        body: staticBody(page.route, page.heading, page.description, lang),
      }),
    );
  }
}

const digest = createHash("sha256").update(template).digest("hex").slice(0, 8);
console.log(
  `prerendered ${objects.length} objects and ${STATIC.en.length} pages ` +
    `in ${LOCALES.length} languages from dist/index.html (${digest}) for ${ORIGIN}`,
);
