/**
 * A history router in one file.
 *
 * The site has eight routes and no nested layouts, so a router dependency would
 * cost more in indirection than it saves. nginx already falls back to
 * index.html for unknown paths, which is all a history router needs.
 *
 * Every page lives under its language, /en/... and /fr/..., the scheme every
 * piighost site links to. The routes below are written without the prefix:
 * the router strips it to match, and `localize` adds it back to a link.
 */

import { i18n, preferredLocale, type Locale } from "./i18n.svelte";

export type Params = Record<string, string>;

export type Match = {
  name: string;
  params: Params;
};

/**
 * The chat demo is off until a model detector exists. Scripted replies over
 * regex hits show nothing the run tab does not already show, and the tab
 * implied a capability the catalog has not shipped. The route, the page, its
 * strings and its analytics event are all kept: turning it back on is this
 * one flag.
 */
export const CHAT_ENABLED: boolean = false;

/** Route patterns, most specific first. `:name` captures one segment. */
const ROUTES: [string, string][] = [
  ["/", "home"],
  ["/labels", "labels"],
  ["/stats", "stats"],
  ["/configs", "configs"],
  ["/playground", "playground"],
  ["/playground/compare", "compare"],
  ["/playground/chat", "chat"],
  ["/contribute", "contribute"],
  ["/r/:namespace/:name", "detail"],
  ["/r/:namespace/:name/:selector", "detail"],
].filter(([, name]) => CHAT_ENABLED || name !== "chat") as [string, string][];

function matchPath(path: string): Match {
  const parts = path.replace(/\/+$/, "").split("/").filter(Boolean);
  for (const [pattern, name] of ROUTES) {
    const expected = pattern.split("/").filter(Boolean);
    if (expected.length !== parts.length) continue;
    const params: Params = {};
    const ok = expected.every((segment, index) => {
      if (segment.startsWith(":")) {
        params[segment.slice(1)] = decodeURIComponent(parts[index]);
        return true;
      }
      return segment === parts[index];
    });
    if (ok) return { name, params };
  }
  return { name: "not-found", params: {} };
}

const PREFIX = /^\/(en|fr)(?=\/|$|\?|#)/;

/** The language a path is under, and the path without it ("/" for the home). */
export function splitLocale(path: string): {
  locale: Locale | null;
  rest: string;
} {
  const match = PREFIX.exec(path);
  if (!match) return { locale: null, rest: path };
  const rest = path.slice(match[0].length);
  return {
    locale: match[1] as Locale,
    rest:
      rest === "" || rest.startsWith("?") || rest.startsWith("#")
        ? `/${rest}`
        : rest,
  };
}

/**
 * The same site path under a language, the page's by default.
 *
 * Only a site path is touched: an absolute URL, a protocol-relative one and a
 * path already under a language come back as they went in. The home is
 * `/en/`, with its slash, the directory nginx serves it from.
 */
export function localize(path: string, locale: Locale = i18n.locale): string {
  if (!path.startsWith("/") || path.startsWith("//")) return path;
  if (splitLocale(path).locale) return path;
  return `/${locale}${path}`;
}

class Router {
  path = $state(location.pathname);
  query = $state(new URLSearchParams(location.search));
  /** The path without its language prefix, which is what the routes match. */
  local = $derived(splitLocale(this.path).rest);
  locale = $derived<Locale>(splitLocale(this.path).locale ?? "en");
  route = $derived(matchPath(this.local));

  constructor() {
    this.prefix();
    addEventListener("popstate", () => this.sync());
  }

  /**
   * Move a path that predates the languages under the browser's.
   *
   * nginx redirects these before the page loads; this covers the development
   * server, and any host that serves the bundle without that rule.
   */
  private prefix() {
    if (splitLocale(location.pathname).locale) return this.sync();
    const to =
      localize(location.pathname, preferredLocale()) +
      location.search +
      location.hash;
    history.replaceState(history.state, "", to);
    this.sync();
  }

  private sync() {
    this.path = location.pathname;
    this.query = new URLSearchParams(location.search);
    i18n.locale = splitLocale(this.path).locale ?? "en";
  }

  /**
   * The current page in another language, query kept: what the language menu
   * links to, so switching never sends a visitor back to the home page.
   */
  alternate(locale: Locale): string {
    return `/${locale}${this.local}${location.search}`;
  }

  /** Navigate, pushing history unless `replace` is set. */
  go(to: string, options: { replace?: boolean } = {}) {
    to = localize(to);
    if (to === this.path + location.search) return;
    history[options.replace ? "replaceState" : "pushState"]({}, "", to);
    this.sync();
    if (!options.replace) scrollTo({ top: 0 });
  }

  /** Replace the query string of the current path, dropping empty values. */
  setQuery(next: URLSearchParams, options: { replace?: boolean } = {}) {
    for (const [key, value] of [...next.entries()]) {
      if (value === "") next.delete(key, value);
    }
    const search = next.toString();
    this.go(this.path + (search ? `?${search}` : ""), options);
  }
}

export const router = new Router();

/**
 * Intercept in-app link clicks so an `<a href>` stays a real link.
 *
 * Keeping real hrefs matters for middle-click, for opening in a new tab and for
 * a crawler, none of which a click handler on a `<div>` would give.
 */
export function interceptLinks(event: MouseEvent) {
  if (event.defaultPrevented || event.button !== 0) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const anchor = (event.target as HTMLElement | null)?.closest("a");
  if (!anchor) return;
  const href = anchor.getAttribute("href");
  if (!href || anchor.target === "_blank" || anchor.hasAttribute("download"))
    return;
  if (!href.startsWith("/") || href.startsWith("//")) return;
  // The API and the files beside the bundle are not pages of the router.
  if (/^\/(api|schema)(\/|$)/.test(href)) return;
  event.preventDefault();
  router.go(href);
}

/** Split `namespace/name:selector` into its pieces, with or without a scheme. */
export function parseRef(ref: string) {
  const body = ref.replace(/^(catalog|hub):(\/\/)?/, "");
  const [key, selector = "latest"] = body.split(":");
  const [namespace, name] = key.split("/");
  return { namespace, name, selector, key };
}

/** The site path of a reference, under the page's language. */
export function refPath(ref: string) {
  const { namespace, name, selector } = parseRef(ref);
  return localize(
    selector === "latest"
      ? `/r/${namespace}/${name}`
      : `/r/${namespace}/${name}/${selector}`,
  );
}
