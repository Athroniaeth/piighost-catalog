<script lang="ts">
  import Loader from "@lucide/svelte/icons/loader-circle";
  import Play from "@lucide/svelte/icons/play";
  import Button from "./ui/Button.svelte";
  import EntityHighlight from "./EntityHighlight.svelte";
  import EntityRow from "./EntityRow.svelte";
  import SamplePicker from "./SamplePicker.svelte";
  import type { SampleOut } from "../generated/api";
  import { ApiError } from "../lib/api";
  import { assignLabelColors } from "../lib/labels";
  import { plural, t } from "../lib/i18n.svelte";
  import { engine, run, type Hit } from "../lib/pyodide.svelte";
  import { TEXTAREA } from "../lib/ui";

  /**
   * Try what is being written, without publishing it and without sending the
   * text anywhere.
   *
   * The caller supplies the catalog, because where it comes from differs and
   * the difference matters. A pattern already holds its own regex, so nothing
   * leaves the browser at all. A group is a list of references, and flattening
   * it is the registry's own rule, so the API does that and there is one
   * implementation of what happens when two sources carry one label.
   *
   * Running it is piighost itself, compiled to WebAssembly in this tab. The
   * text a visitor pastes to see whether their work does what they meant never
   * leaves the machine either way.
   */
  let {
    catalogue,
    ready,
  }: {
    catalogue: () => Promise<Record<string, string>>;
    ready: boolean;
  } = $props();

  let text = $state(
    "Write to john.doe@example.com or call +33 6 39 98 12 34. Card 4111 1111 1111 1111.",
  );
  let hits = $state<Hit[] | null>(null);
  let elapsed = $state(0);
  let error = $state<string | null>(null);
  let busy = $state(false);

  /** The registry's own annotated texts, rather than one anybody must invent. */
  function pick(sample: SampleOut) {
    text = sample.text.trim();
    hits = null;
    error = null;
  }
  const colors = $derived(
    assignLabelColors((hits ?? []).map((hit) => hit.label)),
  );

  async function go() {
    busy = true;
    error = null;
    try {
      const answer = await run(await catalogue(), text);
      hits = answer.hits;
      elapsed = answer.elapsedMs;
    } catch (caught) {
      error = caught instanceof ApiError ? caught.message : String(caught);
      hits = null;
    } finally {
      busy = false;
    }
  }
</script>

<section class="flex min-h-0 min-w-0 flex-col gap-3">
  <!-- One row: the column is narrow, and a heading, a picker and a button on
       three lines push the text itself off the screen. -->
  <div class="flex items-center gap-2">
    <p class="min-w-0 text-xs text-muted-foreground">{t("try.note")}</p>
    <div class="ms-auto flex shrink-0 items-center gap-2">
      <SamplePicker onpick={pick} disabled={busy} />
      <Button
        variant="outline"
        size="sm"
        disabled={busy || !ready}
        onclick={go}
      >
        {#if busy}<Loader class="animate-spin" />{:else}<Play />{/if}
        {busy && !engine.ready ? t("try.loading") : t("try.go")}
      </Button>
    </div>
  </div>

  {#if hits}
    <!-- An API key has no space in it, so `pre-wrap` alone lets one line push
         the whole column sideways. This breaks inside a word and keeps the
         overflow here rather than on the page. -->
    <div
      class="max-h-72 overflow-auto rounded-lg border bg-muted/30 p-3 text-sm [&_p]:break-all"
    >
      <EntityHighlight
        {text}
        hits={hits.map((hit) => ({
          ...hit,
          kept: true,
          detector: "regex",
          pattern: null,
        }))}
        {colors}
      />
    </div>
    <p class="text-xs text-muted-foreground tabular-nums">
      {hits.length}
      {plural("caught", hits.length)} · {elapsed.toFixed(1)} ms
    </p>
    <ul class="space-y-1.5 overflow-y-auto">
      {#each hits as hit, index (index)}
        <EntityRow label={hit.label} text={hit.text} {colors} />
      {/each}
    </ul>
    <Button
      variant="ghost"
      size="sm"
      class="self-start"
      onclick={() => (hits = null)}>{t("play.edit")}</Button
    >
  {:else}
    <textarea
      bind:value={text}
      spellcheck="false"
      aria-label={t("try.text")}
      class="{TEXTAREA} min-h-40"></textarea>
  {/if}

  {#if error}<p class="text-xs text-destructive">{error}</p>{/if}
</section>
