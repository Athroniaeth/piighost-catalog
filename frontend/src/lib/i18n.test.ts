import { afterEach, describe, expect, it } from "vitest";
import { frenchSpacing, i18n, plural } from "./i18n.svelte";

afterEach(() => {
  i18n.locale = "en";
});

describe("plural", () => {
  it("takes the singular for one thing only, in English", () => {
    expect(plural("results", 1)).toBe("result");
    expect(plural("results", 0)).toBe("results");
    expect(plural("uses", 2)).toBe("uses");
  });

  it("takes the singular for zero and one, in French", () => {
    i18n.locale = "fr";
    expect(plural("results", 0)).toBe("résultat");
    expect(plural("results", 1)).toBe("résultat");
    expect(plural("results", 2)).toBe("résultats");
    // Round millions are `many` in French, which falls back to the plural.
    expect(plural("results", 1_000_000)).toBe("résultats");
  });
});

describe("a text from the catalog", () => {
  const text = { en: "Pan-European: IBAN.", fr: "Paneuropéen : IBAN." };

  it("is English on an English page", () => {
    expect(i18n.localized(text)).toEqual({
      text: "Pan-European: IBAN.",
      lang: "en",
    });
  });

  it("is French on a French page, with its no-break spaces", () => {
    i18n.locale = "fr";
    expect(i18n.pick(text)).toBe("Paneuropéen\u00a0: IBAN.");
  });

  it("falls back to English, and says so, where French is missing", () => {
    i18n.locale = "fr";
    expect(i18n.localized({ en: "Only English.", fr: null })).toEqual({
      text: "Only English.",
      lang: "en",
    });
    expect(i18n.localized({ en: "Only English.", fr: "" }).lang).toBe("en");
  });
});

describe("frenchSpacing", () => {
  it("binds : ; ? ! and the guillemets to their word", () => {
    expect(frenchSpacing("Vraiment ? Oui ; « bien » !")).toBe(
      "Vraiment\u00a0? Oui\u00a0; «\u00a0bien\u00a0»\u00a0!",
    );
  });

  it("leaves a URL and a time alone", () => {
    expect(frenchSpacing("https://a.fr à 10:30")).toBe("https://a.fr à 10:30");
  });
});
