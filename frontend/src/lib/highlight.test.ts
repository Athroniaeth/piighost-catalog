import { describe, expect, it } from "vitest";
import { pythonTokens, shellTokens, tomlTokens } from "./highlight";

/** The text of every token carrying this kind, in order. */
function kind(
  tokens: { text: string; kind: string }[],
  name: string,
): string[] {
  return tokens.filter((token) => token.kind === name).map((t) => t.text);
}

describe("pythonTokens", () => {
  it("does not find a keyword inside a longer word", () => {
    // The tokeniser used to walk a slice of the source, and `\b` reads the
    // start of a string as a word boundary: `detector` sliced after `detect`
    // begins with `or`, so every identifier ending in a keyword was painted.
    const tokens = pythonTokens("detector = RegexDetector.from_catalog(ref)");
    expect(kind(tokens, "keyword")).toEqual([]);
  });

  it("finds a keyword standing on its own", () => {
    const tokens = pythonTokens("found = await detector.detect(text)");
    expect(kind(tokens, "keyword")).toEqual(["await"]);
  });

  it("names the callee, the strings and the comments", () => {
    const tokens = pythonTokens(
      '# note\nd = RegexDetector.from_catalog("a/b")',
    );
    expect(kind(tokens, "comment")).toEqual(["# note"]);
    expect(kind(tokens, "function")).toEqual(["from_catalog"]);
    expect(kind(tokens, "string")).toEqual(['"a/b"']);
  });
});

describe("tomlTokens", () => {
  it("reads a section, a key and a literal string", () => {
    const tokens = tomlTokens("[detector]\ntype = 'regex'\n");
    expect(kind(tokens, "section")).toEqual(["[detector]"]);
    expect(kind(tokens, "key")).toEqual(["type"]);
    expect(kind(tokens, "string")).toEqual(["'regex'"]);
  });
});

describe("shellTokens", () => {
  it("only calls the first word of a line a command", () => {
    // `piighost` also appears inside an image name, where it is not one.
    const tokens = shellTokens("docker run ghcr.io/athroniaeth/piighost-api");
    expect(kind(tokens, "command")).toEqual(["docker"]);
  });

  it("only calls a dash after a space a flag", () => {
    const tokens = shellTokens("curl -o out.toml piighost/dev-secrets");
    expect(kind(tokens, "flag")).toEqual(["-o"]);
  });
});
