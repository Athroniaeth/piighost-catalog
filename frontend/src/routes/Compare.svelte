<script lang="ts">
  import Loader from "@lucide/svelte/icons/loader-circle";
  import Plus from "@lucide/svelte/icons/plus";
  import X from "@lucide/svelte/icons/x";
  import type { CompareOut } from "../generated/api";
  import EntityHighlight from "../components/EntityHighlight.svelte";
  import PlaygroundShell from "../components/PlaygroundShell.svelte";
  import RefPicker from "../components/RefPicker.svelte";
  import SamplePicker from "../components/SamplePicker.svelte";
  import Button from "../components/ui/Button.svelte";
  import Region from "../components/ui/Region.svelte";
  import { ApiError, api } from "../lib/api";
  import { plural, t } from "../lib/i18n.svelte";
  import { parseRef, refPath } from "../lib/router.svelte";
  import { assignLabelColors } from "../lib/labels";
  import { EYEBROW, TEXTAREA } from "../lib/ui";

  // A country pack against the international set, on a French text: the pack
  // catches the phone and reads the fourteen digits as a SIRET where the
  // international set can only see a card number. That is the case for groups,
  // in one screen.
  let refs = $state<string[]>([
    "piighost/international",
    "piighost/fr-extended",
  ]);
  let text = $state(
    "Patrick Dupont, 06 39 98 12 34, patrick@example.com, SIRET 732 829 320 00074, 75008 Paris.",
  );
  let result = $state<CompareOut | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);

  const slots = $derived(refs.map((_, index) => index));

  /**
   * The disputed values, under the object that caught them.
   *
   * "Caught by some" said a value was contested without saying by whom, which
   * is the one thing a comparison is for. Grouping is done here rather than
   * asked of the API: the runs already carry every kept hit. An object that
   * caught nothing the others missed gets no heading — its agreement is
   * already the list above.
   */
  const contested = $derived.by(() => {
    const only = new Set(result?.disputed ?? []);
    return (result?.runs ?? [])
      .map((run) => ({
        ref: run.ref,
        values: [
          ...new Set(
            run.hits
              .filter((hit) => hit.kept && only.has(hit.text))
              .map((hit) => hit.text),
          ),
        ].sort(),
      }))
      .filter((group) => group.values.length > 0);
  });
  const colors = $derived(
    assignLabelColors(
      result?.runs.flatMap((run) => run.hits.map((hit) => hit.label)) ?? [],
    ),
  );

  async function go() {
    busy = true;
    error = null;
    try {
      result = await api.compare(refs, text);
    } catch (caught) {
      error = caught instanceof ApiError ? caught.message : String(caught);
      result = null;
    } finally {
      busy = false;
    }
  }
</script>

<PlaygroundShell>
  <Region
    step={1}
    done={result !== null}
    title={t("play.configure")}
    bodyClass="gap-3"
  >
    {#each slots as index (index)}
      <div class="flex items-center gap-1.5">
        <RefPicker
          id="cmp-{index}"
          bind:value={refs[index]}
          label="{t('play.object')} {index + 1}"
        />
        {#if refs.length > 2}
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={t("compare.remove")}
            onclick={() => (refs = refs.filter((_, i) => i !== index))}
          >
            <X />
          </Button>
        {/if}
      </div>
    {/each}
    {#if refs.length < 4}
      <Button
        variant="outline"
        size="sm"
        class="self-start"
        onclick={() => (refs = [...refs, "piighost/generic"])}
      >
        <Plus />
        {t("compare.add")}
      </Button>
    {/if}
    <div class="mt-auto flex flex-col gap-2 pt-2">
      <Button onclick={go} disabled={busy || text.trim() === ""}>
        {#if busy}<Loader class="animate-spin" />{/if}
        {busy ? t("play.running") : t("compare.go")}
      </Button>
      {#if error}<p class="text-xs text-destructive">{error}</p>{/if}
      <p class="text-xs text-muted-foreground">{t("play.privacy")}</p>
    </div>
  </Region>

  <Region
    step={2}
    done={result !== null}
    title={t("play.text")}
    bodyClass="gap-4"
  >
    {#snippet action()}
      <SamplePicker
        onpick={(sample) => (text = sample.text.trim())}
        disabled={busy}
      />
    {/snippet}
    <textarea
      bind:value={text}
      spellcheck="false"
      aria-label={t("play.text")}
      class="{TEXTAREA} min-h-24"></textarea>
    {#if result}
      {#each result.runs as run (run.ref)}
        <div>
          <p class="mb-1.5 font-mono text-xs text-muted-foreground">
            {run.ref} ·
            <span class="tabular-nums"
              >{run.hits.filter((h) => h.kept).length}
              {plural("kept", run.hits.filter((h) => h.kept).length)}</span
            >
          </p>
          <div class="rounded-lg border bg-muted/30 p-3">
            <EntityHighlight {text} hits={run.hits} {colors} />
          </div>
        </div>
      {/each}
    {/if}
  </Region>

  <Region step={3} done={result !== null} title={t("play.results")}>
    {#if !result}
      <p class="text-sm text-muted-foreground">{t("play.empty")}</p>
    {:else}
      <h3 class="{EYEBROW} mb-2">{t("compare.agreed")}</h3>
      <ul class="space-y-1.5">
        {#each result.agreed as value (value)}
          <li class="rounded-md bg-muted/40 p-2 font-mono text-sm">{value}</li>
        {:else}
          <li class="text-sm text-muted-foreground">{t("play.nothing")}</li>
        {/each}
      </ul>
      {#each contested as group (group.ref)}
        <h3 class="{EYEBROW} mt-5 mb-2">
          {t("compare.disputed")}
          <a
            href={refPath(group.ref)}
            class="font-mono normal-case hover:text-foreground hover:underline"
          >
            {parseRef(group.ref).key}
          </a>
        </h3>
        <ul class="space-y-1.5">
          {#each group.values as value (value)}
            <li class="rounded-md bg-muted/40 p-2 font-mono text-sm break-all">
              {value}
            </li>
          {/each}
        </ul>
      {:else}
        <p class="mt-5 text-sm text-muted-foreground">
          {t("compare.noDispute")}
        </p>
      {/each}
    {/if}
  </Region>
</PlaygroundShell>
