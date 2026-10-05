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
 * page now carries the navigation, the catalogue lists every object, and an
 * object page names the groups that use it, its neighbours by tag, and the
 * object before and after it in the index — so the whole registry is walkable
 * from any entry point, which is what a crawler and a reader both need.
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
          description: (body.description ?? {}).en ?? "",
          sources: (data.sources ?? []).map((s) => s.ref).filter(Boolean),
          examples: data.examples ?? {},
        });
      }
    }
  }
  return objects.sort((a, b) => a.key.localeCompare(b.key));
}

/** The routes a reader moves between, on every page, as the header has them. */
const ROUTES = [
  { route: "/", label: "Catalogue" },
  { route: "/labels", label: "Labels" },
  { route: "/configs", label: "Configs" },
  { route: "/playground", label: "Playground" },
  { route: "/contribute", label: "Contribute" },
];

/** The navigation, with the current page left as text rather than a self-link. */
function nav(current) {
  const items = ROUTES.map(({ route, label }) =>
    route === current
      ? `<li>${esc(label)}</li>`
      : `<li><a href="${esc(route)}">${esc(label)}</a></li>`,
  ).join("");
  return `<nav aria-label="Registry"><ul>${items}</ul></nav>`;
}

/** A list of objects as links, each followed by the sentence that names it. */
function objectList(objects) {
  const items = objects
    .map(
      (object) =>
        `<li><a href="/r/${esc(object.key)}">${esc(object.key)}</a>` +
        (object.description
          ? ` — ${esc(summary(object.description, 120))}`
          : "") +
        `</li>`,
    )
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
 * either side of it in the catalogue. The last pair matters most — it chains
 * all 226 pages together, so a crawler that finds one finds the rest without
 * ever going back to the sitemap.
 */
function objectBody(object, neighbours) {
  const parts = [
    nav(null),
    `<h1>${esc(object.key)}</h1>`,
    `<p>${esc(object.description)}</p>`,
  ];
  if (object.label)
    parts.push(`<p>Label: <code>${esc(object.label)}</code></p>`);
  if (object.regex)
    parts.push(`<h2>Pattern</h2><pre><code>${esc(object.regex)}</code></pre>`);
  if (object.sources.length) {
    const items = object.sources
      .map(
        (ref) =>
          `<li><a href="/r/${esc(ref.split(":")[0])}">${esc(ref)}</a></li>`,
      )
      .join("");
    parts.push(`<h2>Sources</h2><ul>${items}</ul>`);
  }
  const matches = object.examples.match ?? [];
  if (matches.length) {
    const items = matches
      .map(
        (e) =>
          `<li><code>${esc(e.text)}</code> → <code>${esc(e.value)}</code></li>`,
      )
      .join("");
    parts.push(`<h2>Must be caught</h2><ul>${items}</ul>`);
  }
  const noMatches = object.examples.no_match ?? [];
  if (noMatches.length) {
    const items = noMatches
      .map((e) => `<li><code>${esc(e.text)}</code></li>`)
      .join("");
    parts.push(`<h2>Must be left alone</h2><ul>${items}</ul>`);
  }
  if (object.tags.length) {
    parts.push(`<p>Tags: ${object.tags.map((t) => esc(t)).join(", ")}</p>`);
  }
  // The API is disallowed in robots.txt, so the link is for the reader; saying
  // so keeps it out of a crawler's queue instead of leaving it to be fetched
  // and refused.
  parts.push(
    `<p><a rel="nofollow" href="/api/v1/refs/${esc(object.key)}/latest/pipeline.toml?part=detector">` +
      `Download the detector as TOML</a></p>`,
  );
  const { usedBy, related, previous, next } = neighbours;
  if (usedBy.length) {
    parts.push(`<h2>Used by</h2>${objectList(usedBy)}`);
  }
  if (related.length) {
    parts.push(`<h2>Related patterns</h2>${objectList(related)}`);
  }
  const around = [
    previous
      ? `<a rel="prev" href="/r/${esc(previous.key)}">← ${esc(previous.key)}</a>`
      : null,
    `<a href="/">All ${esc(object.kind)}s in the catalogue</a>`,
    next
      ? `<a rel="next" href="/r/${esc(next.key)}">${esc(next.key)} →</a>`
      : null,
  ].filter(Boolean);
  parts.push(`<nav aria-label="Catalogue">${around.join(" · ")}</nav>`);
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
function objectJsonLd(object) {
  return {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: object.key,
    description:
      object.description || `The ${object.key} de-identification pattern.`,
    url: `${ORIGIN}/r/${object.key}`,
    identifier: object.key,
    keywords: [
      ...object.tags,
      "PII",
      "de-identification",
      "regex",
      "pseudonymization",
    ],
    license: "https://opensource.org/licenses/MIT",
    isPartOf: { "@type": "DataCatalog", name: "piighost catalog", url: ORIGIN },
    distribution: {
      "@type": "DataDownload",
      encodingFormat: "text/toml",
      contentUrl: `${ORIGIN}/api/v1/refs/${object.key}/latest/pipeline.toml?part=detector`,
    },
  };
}

/** Replace the head metadata of the built document and fill `#app`. */
function render(template, { title, description, canonical, jsonLd, body }) {
  let html = template;
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
  const head = [
    `<link rel="canonical" href="${esc(canonical)}" />`,
    `<meta property="og:url" content="${esc(canonical)}" />`,
    `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>`,
  ].join("\n    ");
  html = html.replace("</head>", `  ${head}\n  </head>`);
  return html.replace(
    '<div id="app"></div>',
    `<div id="app">\n      ${body}\n    </div>`,
  );
}

function write(route, html) {
  const directory = join(DIST, route === "/" ? "." : route.replace(/^\//, ""));
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, "index.html"), html);
}

const template = readFileSync(join(DIST, "index.html"), "utf8");
const objects = readRegistry();
const counts = { pattern: 0, group: 0, config: 0 };
for (const object of objects) counts[object.kind] += 1;

objects.forEach((object, index) => {
  const kindName = object.kind === "config" ? "piighost config" : object.kind;
  write(
    `/r/${object.key}`,
    render(template, {
      title: `${object.key} — ${kindName} — piighost catalog`,
      description: summary(object.description),
      canonical: `${ORIGIN}/r/${object.key}`,
      jsonLd: objectJsonLd(object),
      body: objectBody(object, neighboursOf(object, objects, index)),
    }),
  );
});

/**
 * The bodies of the pages that are not an object.
 *
 * The catalogue lists every object rather than a selection. It is the page a
 * crawler reaches first and the one that carries the most weight, so spending
 * it on a summary and sending the rest to the sitemap was the wrong trade: one
 * page of 226 links is how the registry gets crawled at all.
 */
function staticBody(route, heading, description) {
  const parts = [
    nav(route),
    `<h1>${esc(heading)}</h1>`,
    `<p>${esc(description)}</p>`,
  ];
  const of = (kind) => objects.filter((object) => object.kind === kind);
  if (route === "/") {
    parts.push(`<h2>Patterns</h2>${objectList(of("pattern"))}`);
    parts.push(`<h2>Groups</h2>${objectList(of("group"))}`);
    const configs = of("config");
    if (configs.length)
      parts.push(`<h2>piighost configs</h2>${objectList(configs)}`);
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
        ([label, carriers]) => `<h2>${esc(label)}</h2>${objectList(carriers)}`,
      );
    parts.push(sections.join("\n      "));
  } else if (route === "/configs") {
    const configs = of("config");
    parts.push(
      configs.length
        ? objectList(configs)
        : "<p>No configuration is published yet. The registry holds patterns and groups.</p>",
    );
  } else if (route === "/playground") {
    // Compare is a mode of the playground, not a sibling of it, so it is named
    // here rather than in the navigation. Without this it is in the sitemap
    // with nothing pointing at it, which is how a page gets crawled once and
    // then forgotten.
    parts.push(
      '<p><a href="/playground/compare">Compare several objects on the same ' +
        "text</a>, value by value.</p>",
    );
  }
  if (route === "/") {
    parts.push(
      '<p><a href="/stats">What the registry is asked for</a>: pulls, searches ' +
        "and the objects behind them.</p>",
    );
  }
  return parts.join("\n      ");
}

const STATIC = [
  {
    route: "/",
    title: "piighost catalog — tested de-identification regexes",
    description:
      `A registry of ${counts.pattern} tested de-identification regex patterns and ` +
      `${counts.group} groups for piighost, each carrying the cases it must catch and ` +
      `the cases it must leave alone.`,
    heading: "piighost catalog",
  },
  {
    route: "/labels",
    title: "Labels — piighost catalog",
    description:
      "Every label the registry emits, and the patterns that define it, from EMAIL " +
      "and FR_SIRET to the credential shapes a traceback leaks.",
    heading: "Labels",
  },
  {
    route: "/configs",
    title: "piighost configs — piighost catalog",
    description:
      "Pipelines assembled from the registry's groups: a detector, then what happens " +
      "once something is found.",
    heading: "piighost configs",
  },
  {
    route: "/playground",
    title: "Playground — run a de-identification pattern on your own text",
    description:
      "Run any registry object over a text and see what it catches, what it drops " +
      "and why. Your text is never written to a database.",
    heading: "Playground",
  },
  {
    route: "/playground/compare",
    title: "Compare de-identification patterns — piighost catalog",
    description:
      "Run several registry objects over the same text and see where they disagree, " +
      "value by value.",
    heading: "Compare",
  },
  {
    route: "/contribute",
    title: "Contribute a pattern — piighost catalog",
    description:
      "Propose a regex pattern or a group of patterns. Checked here with the " +
      "maintainers' own tests, merged by pull request.",
    heading: "Contribute",
  },
  {
    route: "/stats",
    title: "Usage — piighost catalog",
    description:
      "What the registry is asked for: pulls, searches and the objects behind them.",
    heading: "Usage",
  },
];

const catalog = {
  "@context": "https://schema.org",
  "@type": "DataCatalog",
  name: "piighost catalog",
  url: ORIGIN,
  description:
    "A registry of tested de-identification regexes for piighost: patterns, and the " +
    "groups that compose them.",
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
    target: `${ORIGIN}/?q={search_term_string}`,
    "query-input": "required name=search_term_string",
  },
};

for (const page of STATIC) {
  write(
    page.route,
    render(template, {
      title: page.title,
      description: page.description,
      canonical: `${ORIGIN}${page.route}`,
      jsonLd: catalog,
      body: staticBody(page.route, page.heading, page.description),
    }),
  );
}

const digest = createHash("sha256").update(template).digest("hex").slice(0, 8);
console.log(
  `prerendered ${objects.length} objects and ${STATIC.length} pages ` +
    `from dist/index.html (${digest}) for ${ORIGIN}`,
);
