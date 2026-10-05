<script lang="ts">
  import { frenchSpacing, i18n, type Localized } from "../lib/i18n.svelte";

  /**
   * A text from the catalog, a description or a title, in the page's language.
   *
   * The manifests mark a group or a label name with Markdown backticks, which
   * rendered as literal backticks; a pair becomes a code span here, and an odd
   * one out stays as typed. French is optional in a manifest, so a French page
   * may show the English text: `lang` then says so, for a screen reader's voice
   * and the browser's hyphenation.
   */
  let { text }: { text: Localized } = $props();

  const shown = $derived(i18n.localized(text));
  const parts = $derived.by(() => {
    const pieces = shown.text.split("`");
    // An even count of pieces means an unpaired backtick: glue the last back.
    if (pieces.length % 2 === 0) {
      const last = pieces.pop() ?? "";
      pieces[pieces.length - 1] += "`" + last;
    }
    return pieces.map((piece, index) => ({
      code: index % 2 === 1,
      text:
        index % 2 === 0 && shown.lang === "fr" ? frenchSpacing(piece) : piece,
    }));
  });
</script>

<span lang={shown.lang === i18n.locale ? undefined : shown.lang}
  >{#each parts as part, index (index)}{#if part.code}<code
        class="rounded bg-muted px-1 py-px font-mono text-[0.9em]"
        >{part.text}</code
      >{:else}{part.text}{/if}{/each}</span
>
