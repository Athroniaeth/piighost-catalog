import { mount } from "svelte";
import App from "./App.svelte";
import { startAnalytics } from "./lib/analytics";
// hub.css imports the generated tokens (app.css) first, then the catalog's own
// rules: one Tailwind build, which also scans @piighost/ui.
import "./hub.css";

// Before the app mounts, so the first screen view is the one the visitor
// actually landed on rather than the one they navigated to next.
startAnalytics();

const target = document.getElementById("app");

if (!target) {
  throw new Error("Root element #app not found");
}

// The document arrives with the page already in it, written by
// scripts/prerender.mjs so a crawler that runs no JavaScript still reads the
// registry. Svelte 5 appends rather than replaces, so the prerendered copy has
// to go, or the visitor sees the page twice.
target.innerHTML = "";

const app = mount(App, {
  target,
});

export default app;
