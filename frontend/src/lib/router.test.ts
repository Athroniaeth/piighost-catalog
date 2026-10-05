import { describe, expect, it } from "vitest";
import { CHAT_ENABLED, parseRef, refPath, router } from "./router.svelte";

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
    expect(refPath("piighost/fr-default")).toBe("/r/piighost/fr-default");
    expect(refPath("piighost/fr-default:latest")).toBe(
      "/r/piighost/fr-default",
    );
  });

  it("keeps a commit in the URL", () => {
    expect(refPath("piighost/fr-default:3fa9c2e1")).toBe(
      "/r/piighost/fr-default/3fa9c2e1",
    );
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
