import { describe, expect, it } from "vitest";
import { i18n } from "./i18n.svelte";
import {
  CHAT_ENABLED,
  localize,
  parseRef,
  refPath,
  router,
  splitLocale,
} from "./router.svelte";

describe("parseRef", () => {
  it("splits a bare key, defaulting the selector to latest", () => {
    expect(parseRef("piighost/fr-default")).toEqual({
      namespace: "piighost",
      name: "fr-default",
      selector: "latest",
      key: "piighost/fr-default",
    });
  });

  it("reads a commit selector after the colon", () => {
    expect(parseRef("piighost/fr-default:3fa9c2e1").selector).toBe("3fa9c2e1");
  });

  it("strips the catalog prefix in both its written forms", () => {
    expect(parseRef("catalog:piighost/fr-default:prod").selector).toBe("prod");
    expect(parseRef("catalog://piighost/fr-default").key).toBe(
      "piighost/fr-default",
    );
  });

  it("still reads the older hub prefix", () => {
    expect(parseRef("hub:piighost/fr-default:prod").selector).toBe("prod");
  });
});

describe("refPath", () => {
  it("leaves latest out of the URL, since the bare name means latest", () => {
    expect(refPath("piighost/fr-default")).toBe("/en/r/piighost/fr-default");
    expect(refPath("piighost/fr-default:latest")).toBe(
      "/en/r/piighost/fr-default",
    );
  });

  it("keeps a commit in the URL", () => {
    expect(refPath("piighost/fr-default:3fa9c2e1")).toBe(
      "/en/r/piighost/fr-default/3fa9c2e1",
    );
  });
});

describe("languages", () => {
  it("reads the language off the path, and the path the routes match", () => {
    expect(splitLocale("/fr/r/piighost/jwt")).toEqual({
      locale: "fr",
      rest: "/r/piighost/jwt",
    });
    expect(splitLocale("/en")).toEqual({ locale: "en", rest: "/" });
    expect(splitLocale("/en/?q=iban")).toEqual({
      locale: "en",
      rest: "/?q=iban",
    });
    // A path that merely starts with the letters is not under a language.
    expect(splitLocale("/frobnicate").locale).toBeNull();
  });

  it("puts a site path under a language, and leaves the rest alone", () => {
    expect(localize("/", "fr")).toBe("/fr/");
    expect(localize("/?tag=fr", "fr")).toBe("/fr/?tag=fr");
    expect(localize("/configs", "en")).toBe("/en/configs");
    expect(localize("/fr/configs", "en")).toBe("/fr/configs");
    expect(localize("https://piighost.dev/fr/", "en")).toBe(
      "https://piighost.dev/fr/",
    );
    expect(localize("//example.com/", "en")).toBe("//example.com/");
  });

  it("moved the unprefixed page it started on under the browser's language", () => {
    // jsdom starts on / and says en-US.
    expect(router.path.startsWith("/en")).toBe(true);
  });

  it("follows the language of the path, and keeps the page across a switch", () => {
    router.go("/fr/configs?x=1");
    expect(i18n.locale).toBe("fr");
    expect(router.route.name).toBe("configs");
    expect(router.alternate("en")).toBe("/en/configs?x=1");
    // A link written without a language stays in the page's.
    router.go("/contribute");
    expect(router.path).toBe("/fr/contribute");
    router.go(router.alternate("en"));
    expect(i18n.locale).toBe("en");
    expect(router.path).toBe("/en/contribute");
  });
});

describe("router", () => {
  it("matches the static routes", () => {
    router.go("/playground/compare");
    expect(router.route.name).toBe("compare");
    router.go("/configs");
    expect(router.route.name).toBe("configs");
    router.go("/contribute");
    expect(router.route.name).toBe("contribute");
    router.go("/");
    expect(router.route.name).toBe("home");
  });

  it("does not match the chat route while the demo is off", () => {
    router.go("/playground/chat");
    expect(router.route.name).toBe(CHAT_ENABLED ? "chat" : "not-found");
  });

  it("captures the parameters of a detail route", () => {
    router.go("/r/piighost/fr-default/3fa9c2e1");
    expect(router.route.name).toBe("detail");
    expect(router.route.params).toEqual({
      namespace: "piighost",
      name: "fr-default",
      selector: "3fa9c2e1",
    });
  });

  it("falls through to not-found rather than matching loosely", () => {
    router.go("/nope");
    expect(router.route.name).toBe("not-found");
    router.go("/playground/nope");
    expect(router.route.name).toBe("not-found");
  });

  it("drops empty values when replacing the query", () => {
    router.go("/");
    router.setQuery(
      new URLSearchParams([
        ["q", "iban"],
        ["kind", ""],
      ]),
    );
    expect(location.search).toBe("?q=iban");
  });
});
