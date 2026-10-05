/* Sets .dark before first paint: the page arrives prerendered, and a class set
 * by the app bundle would come after the first frame, a flash of the light
 * theme on every visit. A separate file rather than an inline script: the
 * production CSP is `script-src 'self'` with no `unsafe-inline`. Deliberately
 * neither a module nor deferred: it has to run before the page is painted.
 *
 * The key is the ecosystem's, piighost-theme (THEME_STORAGE_KEY in
 * @piighost/ui). A choice saved under the catalog's former key,
 * piighost-hub-theme, is moved over once, so no visitor loses it. */
(function () {
  try {
    var key = "piighost-theme";
    var former = localStorage.getItem("piighost-hub-theme");
    if (former !== null) {
      if (localStorage.getItem(key) === null) localStorage.setItem(key, former);
      localStorage.removeItem("piighost-hub-theme");
    }
    if (localStorage.getItem(key) !== "light") {
      document.documentElement.classList.add("dark");
    }
  } catch (_) {
    /* storage refused, strict private browsing: dark, the default. */
    document.documentElement.classList.add("dark");
  }
})();
