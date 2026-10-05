/**
 * A pattern, as a form rather than as TOML.
 *
 * Contributing a regex through a manifest textarea asks someone to learn the
 * file format before they can propose a shape they already know. Everything a
 * `pattern.toml` needs is a handful of fields and two lists of examples, so the
 * page asks for those and writes the file itself.
 *
 * The rendering lives here rather than in the component because it is the part
 * that can be wrong in ways nobody sees until the check runs: a quote inside a
 * description, a backslash in an example, a regex holding the very character
 * that closes a TOML literal string.
 */

import type { CommitDetail } from "../generated/api";

export type Example = { text: string; value: string };

export type PatternDraft = {
  name: string;
  label: string;
  tags: string[];
  regex: string;
  en: string;
  matches: Example[];
  noMatches: { text: string }[];
  redos: { prefix: string; filler: string; suffix: string };
};

/**
 * What an empty form suggests, taken from the registry's own `email` pattern.
 *
 * A placeholder is the shortest documentation anyone reads, so it shows a
 * pattern that exists and passes every check rather than an invented order
 * number: a real regex with its lookbehind, two sentences that must be caught,
 * two that must not, and a backtracking recipe whose filler actually makes the
 * engine work. Copy it verbatim and the check goes green, which is the fastest
 * way to learn what each field is for.
 */
export const PLACEHOLDER = {
  name: "email",
  label: "EMAIL",
  regex:
    "(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\\.)+[A-Za-z]{2,}",
  en: "Email address, simplified RFC 5322. The lookbehind pins the start of the local part.",
  matches: [
    {
      text: "Write to john.doe@example.com for any question.",
      value: "john.doe@example.com",
    },
    {
      text: "Contact: support+billing@mail.example.org",
      value: "support+billing@mail.example.org",
    },
  ],
  noMatches: [{ text: "not an email" }, { text: "john@doe" }],
  redos: { prefix: "john.doe@example.com ", filler: "a.", suffix: "@" },
} as const;

export function emptyDraft(): PatternDraft {
  return {
    name: "",
    label: "",
    tags: [],
    regex: "",
    en: "",
    matches: [
      { text: "", value: "" },
      { text: "", value: "" },
    ],
    noMatches: [{ text: "" }, { text: "" }],
    redos: { prefix: "", filler: "", suffix: "" },
  };
}

/** `ORDER_ID` out of `order-id`: the label convention is upper snake. */
export function labelOf(name: string): string {
  return name.toUpperCase().replace(/-/g, "_");
}

/** A TOML basic string: only the quote and the backslash need escaping. */
function quoted(value: string): string {
  const escaped = value
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\n")
    .replace(/\t/g, "\\t");
  return `"${escaped}"`;
}

export type Problem = { field: string; message: string };

/** Whether anything has been typed yet, so a fresh form is not a list of faults. */
export function started(draft: PatternDraft): boolean {
  return (
    draft.regex.trim() !== "" ||
    draft.label.trim() !== "" ||
    draft.tags.length > 0 ||
    draft.en.trim() !== "" ||
    draft.matches.some((row) => row.text !== "" || row.value !== "") ||
    draft.noMatches.some((row) => row.text !== "") ||
    Object.values(draft.redos).some((value) => value !== "")
  );
}

const NAME = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const LABEL = /^[A-Z][A-Z0-9_]*$/;

/**
 * Everything the registry would reject, reported at once.
 *
 * Deliberately only the rules a browser can settle on its own: shape, presence,
 * TOML safety. Whether the regex actually catches its examples is a question
 * for the Python engine, which the page asks the API, and whether the result
 * survives composition is a question for the check.
 */
export function problems(draft: PatternDraft): Problem[] {
  const found: Problem[] = [];
  if (!NAME.test(draft.name))
    found.push({ field: "name", message: "name.kebab" });
  if (!LABEL.test(draft.label))
    found.push({ field: "label", message: "label.snake" });
  if (draft.tags.length === 0)
    found.push({ field: "tags", message: "tags.empty" });
  if (draft.regex.trim() === "")
    found.push({ field: "regex", message: "regex.empty" });
  // A TOML literal string has no escape, so a single quote inside it ends the
  // string early and the manifest stops parsing where nobody would look.
  if (draft.regex.includes("'"))
    found.push({ field: "regex", message: "regex.quote" });
  if (draft.en.trim() === "")
    found.push({ field: "en", message: "description.empty" });
  if (/[\u2014\u2013]/.test(draft.en))
    found.push({ field: "en", message: "description.dash" });

  const matches = draft.matches.filter(
    (example) => example.text.trim() !== "" || example.value.trim() !== "",
  );
  if (matches.length < 2)
    found.push({ field: "matches", message: "matches.two" });
  for (const [index, example] of matches.entries()) {
    if (example.value.trim() === "" || example.text.trim() === "") {
      found.push({ field: `match.${index}`, message: "match.incomplete" });
      continue;
    }
    // The registry requires the value to appear exactly once, so that the
    // expected span is never ambiguous.
    const occurrences = example.text.split(example.value).length - 1;
    if (occurrences !== 1)
      found.push({ field: `match.${index}`, message: "match.once" });
  }

  const noMatches = draft.noMatches.filter((row) => row.text.trim() !== "");
  if (noMatches.length < 2)
    found.push({ field: "noMatches", message: "noMatches.two" });

  // The prefix may legitimately be empty: a pattern anchored on a word
  // boundary has nothing valid to put in front of the ambiguous fragment.
  const { filler, suffix } = draft.redos;
  if (filler.trim() === "" || suffix.trim() === "")
    found.push({ field: "redos", message: "redos.incomplete" });
  return found;
}

/** The `pattern.toml` this draft describes. */
export function toManifest(draft: PatternDraft): string {
  const matches = draft.matches
    .filter((example) => example.text !== "" && example.value !== "")
    .map(
      (example) =>
        `\n[[examples.match]]\ntext = ${quoted(example.text)}\nvalue = ${quoted(example.value)}\n`,
    )
    .join("");
  const noMatches = draft.noMatches
    .filter((row) => row.text !== "")
    .map((row) => `\n[[examples.no_match]]\ntext = ${quoted(row.text)}\n`)
    .join("");
  const tags = draft.tags.map((tag) => `"${tag}"`).join(", ");

  return `schema_version = 1

[pattern]
name = "${draft.name}"
label = "${draft.label}"
tags = [${tags}]
regex = '${draft.regex}'

[pattern.description]
en = ${quoted(draft.en)}
${matches}${noMatches}
[redos]
prefix = ${quoted(draft.redos.prefix)}
filler = ${quoted(draft.redos.filler)}
suffix = ${quoted(draft.redos.suffix)}
`;
}

/**
 * A draft from a pattern already in the registry.
 *
 * Read from the frozen commit rather than from the TOML, because the API
 * already hands back what Python's own parser made of the file. Parsing TOML
 * in the browser to fill a form would be a second implementation of the format,
 * and the first one it disagreed with would be the one that decides whether the
 * submission is accepted.
 *
 * Everything is copied, including the examples, because forking a pattern means
 * changing its shape and keeping the cases it already got right.
 */
export function draftFrom(commit: CommitDetail): PatternDraft {
  const content = commit.content as {
    name?: string;
    label?: string;
    regex?: string;
    tags?: string[];
    description?: { en?: string; fr?: string };
    examples?: {
      match?: { text?: string; value?: string }[];
      no_match?: { text?: string }[];
    };
    redos?: { prefix?: string; filler?: string; suffix?: string };
  };

  const matches = (content.examples?.match ?? []).map((example) => ({
    text: example.text ?? "",
    value: example.value ?? "",
  }));
  const noMatches = (content.examples?.no_match ?? []).map((row) => ({
    text: row.text ?? "",
  }));

  return {
    name: content.name ?? "",
    label: content.label ?? "",
    tags: [...(content.tags ?? [])],
    regex: content.regex ?? "",
    en: content.description?.en ?? "",
    // A fork of a pattern with a single example would open on one row and look
    // like the form had lost one, so the minimum the registry asks for is also
    // the minimum shown.
    matches:
      matches.length >= 2
        ? matches
        : [...matches, ...emptyDraft().matches].slice(0, 2),
    noMatches:
      noMatches.length >= 2
        ? noMatches
        : [...noMatches, ...emptyDraft().noMatches].slice(0, 2),
    redos: {
      prefix: content.redos?.prefix ?? "",
      filler: content.redos?.filler ?? "",
      suffix: content.redos?.suffix ?? "",
    },
  };
}
