<script lang="ts">
  import type { SampleOut } from "../generated/api";
  import { api } from "../lib/api";
  import { i18n, t } from "../lib/i18n.svelte";

  /**
   * The studio's sample picker: a select that resets to its placeholder after
   * each pick, so the same sample can be loaded twice.
   */
  let {
    onpick,
    disabled = false,
  }: { onpick: (sample: SampleOut) => void; disabled?: boolean } = $props();

  const samples = api.samples();
</script>

{#await samples then result}
  <select
    aria-label={t("play.sample")}
    {disabled}
    value=""
    class="max-w-full min-w-0 truncate rounded-md border bg-background px-2 py-1 text-xs"
    onchange={(event) => {
      const select = event.currentTarget;
      const sample = result.items.find((s) => s.name === select.value);
      if (sample) onpick(sample);
      select.selectedIndex = 0;
    }}
  >
    <option value="">{t("play.sample")}</option>
    {#each result.items as sample (sample.name)}
      <option value={sample.name}>{i18n.pick(sample.title)}</option>
    {/each}
  </select>
{/await}
