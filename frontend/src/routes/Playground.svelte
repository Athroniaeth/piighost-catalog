<script lang="ts">
  import Loader from "@lucide/svelte/icons/loader-circle";
  import Play from "@lucide/svelte/icons/play";
  import type { RunOut, SampleOut } from "../generated/api";
  import EntityHighlight from "../components/EntityHighlight.svelte";
  import EntityRow from "../components/EntityRow.svelte";
  import PlaceholderText from "../components/PlaceholderText.svelte";
  import PlaygroundShell from "../components/PlaygroundShell.svelte";
  import RefPicker from "../components/RefPicker.svelte";
  import SamplePicker from "../components/SamplePicker.svelte";
  import Button from "../components/ui/Button.svelte";
  import Region from "../components/ui/Region.svelte";
  import Segmented from "../components/ui/Segmented.svelte";
  import { track } from "../lib/analytics";
  import { ApiError, api } from "../lib/api";
  import { plural, t } from "../lib/i18n.svelte";
  import { assignLabelColors } from "../lib/labels";
  import { refPath, router } from "../lib/router.svelte";
  import { EYEBROW, FIELD_MONO, TEXTAREA } from "../lib/ui";

  // Written as a constant: inside an attribute, Svelte would read the `{6}` of a
  // regex quantifier as an expression and render a bare 6.
  const REGEX_PLACEHOLDER = String.raw`\bORD-[0-9]{6}\b`;

  let source = $state<"object" | "candidate">("object");
  // The widest group, and the one the first sample is written for: a traceback
  // pasted into an assistant, where the credentials are the accident.
  let ref = $state(router.query.get("ref") ?? "piighost/logs");
  let regex = $state("");
  let text = $state("");
  let view = $state<"input" | "anonymized">("input");
  let run = $state<RunOut | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);

  // The page opens on the first sample: an empty box asks the visitor to invent
  // a text holding personal data, which is the slowest possible way to see what
  // the catalog does.
  api.samples().then((result) => {
    const first = result.items[0];
    if (first && text === "") text = first.text.trim();
  });

  const kept = $derived(run?.hits.filter((hit) => hit.kept) ?? []);
  const dropped = $derived(run?.hits.filter((hit) => !hit.kept) ?? []);
  const colors = $derived(
    assignLabelColors(run?.hits.map((hit) => hit.label) ?? []),
  );
  const runnable = $derived(
    text.trim() !== "" &&
      (source === "object" ? ref !== "" : regex.trim() !== ""),
  );

  const sourceOptions = $derived([
    { value: "object" as const, label: t("play.object") },
    { value: "candidate" as const, label: t("play.candidate") },
  ]);
  const viewOptions = $derived([
    { value: "input" as const, label: t("play.input") },
    { value: "anonymized" as const, label: t("play.anonymized") },
  ]);

  async function go() {
    busy = true;
    error = null;
    try {
      run =
        source === "object"
          ? await api.run(ref, text)
          : await api.candidate(regex, text, "CANDIDATE");
      view = "anonymized";
      track({
        name: "playground_run",
        props: {
          source,
          kept: run.hits.filter((hit) => hit.kept).length,
          elapsedMs: Math.round(run.elapsed_ms),
        },
      });
    } catch (caught) {
      error = caught instanceof ApiError ? caught.message : String(caught);
      run = null;
    } finally {
      busy = false;
    }
  }

  function edit() {
    run = null;
    view = "input";
  }

  function pick(sample: SampleOut) {
    text = sample.text.trim();
    edit();
  }

  /** `email` out of `piighost/email:9d3fba58`: the column is narrow. */
  function shortName(ref: string): string {
    return ref.split("/").pop()?.split(":")[0] ?? ref;
  }

  /** Which kept detection took a dropped one's span, for the results column. */
  function winnerOf(index: number): string | null {
    const lost = dropped[index];
    const winner = kept.find(
      (hit) => hit.start < lost.end && hit.end > lost.start,
    );
    return winner ? winner.label : null;
  }
</script>

<PlaygroundShell>
  <Region
    step={1}
    done={run !== null}
    title={t("play.configure")}
    bodyClass="gap-4"
  >
    <Segmented
      options={sourceOptions}
      bind:value={source}
      label={t("play.configure")}
    />

    {#if source === "object"}
      <RefPicker id="play-ref" bind:value={ref} label={t("play.object")} />
    {:else}
      <div class="space-y-1.5">
        <input
          bind:value={regex}
          placeholder={REGEX_PLACEHOLDER}
          aria-label={t("play.regexPlaceholder")}
          spellcheck="false"
          class={FIELD_MONO}
        />
        <p class="text-xs text-muted-foreground">{t("play.candidateNote")}</p>
      </div>
    {/if}

    <div class="mt-auto flex flex-col gap-2 pt-2">
      <Button onclick={go} disabled={busy || !runnable}>
        {#if busy}<Loader class="animate-spin" />{:else}<Play />{/if}
        {busy ? t("play.running") : t("play.go")}
      </Button>
      <div class="flex flex-col gap-1 text-xs text-muted-foreground">
        {#if run}
          <p class="tabular-nums">
            {run.elapsed_ms.toFixed(1)}
            {t("play.elapsed")} · {kept.length}
            {plural("kept", kept.length)}
          </p>
          {#if run.truncated}<p>{t("play.truncated")}</p>{/if}
          {#if run.unsupported.length > 0}
            <p>
              {t("play.unsupported")}
              <span class="font-mono">{run.unsupported.join(", ")}</span>
            </p>
          {/if}
        {/if}
        {#if error}<p class="text-destructive">{error}</p>{/if}
        <p>{t("play.privacy")}</p>
      </div>
    </div>
  </Region>

  <Region step={2} done={run !== null} title={t("play.text")}>
    {#snippet action()}
      <div class="flex min-w-0 flex-wrap items-center gap-2">
        {#if run}
          <Segmented
            options={viewOptions}
            bind:value={view}
            label={t("play.text")}
          />
        {/if}
        <SamplePicker onpick={pick} disabled={busy} />
      </div>
    {/snippet}

    {#if run && view === "anonymized"}
      <div class="flex-1 overflow-auto rounded-lg border bg-muted/30 p-3">
        <PlaceholderText text={run.anonymized_text} {colors} />
      </div>
    {:else if run}
      <div class="flex-1 rounded-lg border bg-muted/30 p-3">
        <EntityHighlight {text} hits={run.hits} {colors} />
      </div>
      <Button variant="outline" size="sm" class="mt-2 self-start" onclick={edit}
        >{t("play.edit")}</Button
      >
    {:else}
      <textarea
        bind:value={text}
        spellcheck="false"
        aria-label={t("play.text")}
        class="{TEXTAREA} flex-1"></textarea>
    {/if}
  </Region>

  <Region step={3} done={kept.length > 0} title={t("play.results")}>
    {#if !run}
      <p class="text-sm text-muted-foreground">{t("play.empty")}</p>
    {:else if run.hits.length === 0}
      <p class="text-sm text-muted-foreground">{t("play.nothing")}</p>
    {:else}
      <ul class="space-y-1.5">
        {#each kept as hit, index (index)}
          <EntityRow label={hit.label} text={hit.text} {colors}>
            {#snippet trailing()}
              {#if hit.pattern}<a
                  href={refPath(hit.pattern)}
                  class="font-mono hover:underline">{shortName(hit.pattern)}</a
                >{/if}
            {/snippet}
          </EntityRow>
        {/each}
      </ul>
      {#if dropped.length > 0}
        <h3 class="{EYEBROW} mt-5 mb-2">{t("play.dropped")}</h3>
        <ul class="space-y-1.5">
          {#each dropped as hit, index (index)}
            <EntityRow label={hit.label} text={hit.text} {colors} muted>
              {#snippet trailing()}
                {#if winnerOf(index)}{t("play.lostTo")}
                  <span class="font-mono">{winnerOf(index)}</span>{/if}
              {/snippet}
            </EntityRow>
          {/each}
        </ul>
      {/if}
    {/if}
  </Region>
</PlaygroundShell>
