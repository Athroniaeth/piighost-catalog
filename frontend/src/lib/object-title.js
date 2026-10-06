/**
 * What an object page is called: its heading, its tab title, its name in
 * schema.org.
 *
 * Plain JavaScript, because two programs need the exact same words.
 * scripts/prerender.mjs writes them into the static page, for a crawler and for
 * the first paint. The application writes them again once it has mounted. If
 * the two disagreed, the title would change under the visitor on load.
 *
 * The page leads with the readable name, `SIRET (France)`, because that is what
 * people search for. Nobody types `fr-siret`, so the identifier moves to a line
 * above the heading and stays the schema.org `identifier`. A manifest written
 * without a `title` keeps the identifier as its heading, as before.
 */

/** The site's name after the page's, as the French and English pages say it. */
export const SITE = { en: "piighost catalog", fr: "catalogue piighost" };

/** What the page is, after the colon. */
const KIND = {
  en: {
    pattern: "tested pattern",
    group: "tested group",
    config: "piighost config",
  },
  fr: {
    pattern: "motif testé",
    group: "groupe testé",
    config: "config piighost",
  },
};

/** French puts a no-break space before a colon, as lib/i18n.svelte.ts does. */
const COLON = { en: ":", fr: " :" };

/**
 * The title in a language, and the language it is really in: the English one
 * stands in where a manifest has no French.
 *
 * @param {{ title?: { en: string, fr?: string | null } | null }} object
 * @param {"en" | "fr"} lang
 * @returns {{ text: string, lang: "en" | "fr" } | null}
 */
export function titleOf(object, lang) {
  const title = object.title;
  if (!title) return null;
  if (lang === "fr" && title.fr) return { text: title.fr, lang: "fr" };
  return { text: title.en, lang: "en" };
}

/** @param {string} text */
function upperFirst(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * The page heading: `SIRET (France)`, `Phone number (France)`. A title is
 * written as it reads mid-sentence, so the heading capitalises it.
 *
 * @param {{ key: string, title?: { en: string, fr?: string | null } | null }} object
 * @param {"en" | "fr"} lang
 */
export function headingOf(object, lang) {
  const title = titleOf(object, lang);
  return title ? upperFirst(title.text) : object.key;
}

/**
 * The name a search matches: `Regex SIRET (France)`. A config is a pipeline
 * rather than a regex, so it keeps its heading.
 *
 * @param {{ key: string, kind: string, title?: { en: string, fr?: string | null } | null }} object
 * @param {"en" | "fr"} lang
 */
export function searchNameOf(object, lang) {
  const title = titleOf(object, lang);
  if (!title) return object.key;
  return object.kind === "config"
    ? upperFirst(title.text)
    : `Regex ${title.text}`;
}

/**
 * The tab title: `Regex SIRET (France): tested pattern · piighost catalog`.
 * Without a title, the identifier and the kind, as the pages had before.
 *
 * @param {{ key: string, kind: string, title?: { en: string, fr?: string | null } | null }} object
 * @param {"en" | "fr"} lang
 * @param {string} kindName What the kind is called, for an object without a title.
 */
export function pageTitleOf(object, lang, kindName) {
  if (!object.title) return `${object.key} · ${kindName} · ${SITE[lang]}`;
  const kind = KIND[lang][/** @type {"pattern"} */ (object.kind)] ?? kindName;
  return `${searchNameOf(object, lang)}${COLON[lang]} ${kind} · ${SITE[lang]}`;
}
