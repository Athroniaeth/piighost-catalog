/**
 * Dark by default, light on request, remembered (charter v3, as piighost.dev).
 * The system preference is ignored on purpose: a marketing site and its tools
 * should look identical in a screenshot and on the visitor's screen.
 *
 * public/theme.js sets the class before first paint, since the page arrives
 * prerendered; this module only keeps the state and the toggle.
 */

import { THEME_STORAGE_KEY as STORAGE_KEY } from "@piighost/ui";

// The ecosystem's key, piighost-theme. public/theme.js moves a choice saved
// under the catalog's former key, piighost-hub-theme, before this module runs.

class Theme {
  dark = $state(localStorage.getItem(STORAGE_KEY) !== "light");

  constructor() {
    this.apply();
  }

  toggle() {
    this.dark = !this.dark;
    localStorage.setItem(STORAGE_KEY, this.dark ? "dark" : "light");
    this.apply();
  }

  private apply() {
    document.documentElement.classList.toggle("dark", this.dark);
  }
}

export const theme = new Theme();
