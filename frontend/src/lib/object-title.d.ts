// Types for object-title.js, which stays JavaScript so that
// scripts/prerender.mjs can import it without a build step.

type Lang = "en" | "fr";
type Titled = {
  key: string;
  kind: string;
  title?: { en: string; fr?: string | null } | null;
};

export const SITE: Record<Lang, string>;
export function titleOf(
  object: Pick<Titled, "title">,
  lang: Lang,
): { text: string; lang: Lang } | null;
export function headingOf(
  object: Pick<Titled, "key" | "title">,
  lang: Lang,
): string;
export function searchNameOf(object: Titled, lang: Lang): string;
export function pageTitleOf(
  object: Titled,
  lang: Lang,
  kindName: string,
): string;
