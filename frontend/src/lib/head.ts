import { LOCALES, type Locale } from "./i18n.svelte";

/**
 * The head tags the page's language decides, kept true after a navigation.
 *
 * scripts/prerender.mjs writes them into each page, for a crawler that runs no
 * JavaScript. The router then changes the page without a load, so the same
 * tags are rewritten here: `lang`, which a screen reader takes its voice from,
 * the canonical URL, and one alternate per language plus `x-default`, English,
 * for a visitor whose language is neither.
 */
export function syncHead(locale: Locale, local: string) {
  document.documentElement.lang = locale;
  const url = (lang: Locale) => `${location.origin}/${lang}${local}`;
  setLink("canonical", url(locale));
  for (const lang of LOCALES) setLink("alternate", url(lang), lang);
  setLink("alternate", url("en"), "x-default");
  setMeta("og:url", url(locale));
  setMeta("og:locale", locale === "fr" ? "fr_FR" : "en_US");
}

function setLink(rel: string, href: string, hreflang?: string) {
  const selector = hreflang
    ? `link[rel="${rel}"][hreflang="${hreflang}"]`
    : `link[rel="${rel}"]:not([hreflang])`;
  let element = document.head.querySelector<HTMLLinkElement>(selector);
  if (!element) {
    element = document.createElement("link");
    element.rel = rel;
    if (hreflang) element.hreflang = hreflang;
    document.head.append(element);
  }
  element.href = href;
}

function setMeta(property: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(
    `meta[property="${property}"]`,
  );
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute("property", property);
    document.head.append(element);
  }
  element.content = content;
}
