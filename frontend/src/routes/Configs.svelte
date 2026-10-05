<script lang="ts">
  import Async from "../components/Async.svelte";
  import ObjectRow from "../components/ObjectRow.svelte";
  import { api } from "../lib/api";
  import { t } from "../lib/i18n.svelte";

  /**
   * The piighost configurations, on their own page.
   *
   * They used to sit in the catalog beside the patterns and the groups,
   * where 32 pipelines among 186 regexes made the catalog read as a config store.
   * A configuration is a different object: it names a detector, then decides
   * what happens once something is found. The registry's own subject is the
   * regexes, so these live next door rather than in the middle.
   */
  const configs = api.search({ kind: ["config"], sort: "labels" });
</script>

<div class="mx-auto max-w-4xl px-4 py-8">
  <h1 class="text-2xl font-bold tracking-tight">{t("configs.title")}</h1>
  <p class="mt-2 max-w-2xl text-sm text-muted-foreground">
    {t("configs.lede")}
  </p>
  <Async promise={configs}>
    {#snippet children(result)}
      <ul class="mt-6 space-y-3">
        {#each result.items as item (item.key)}
          <ObjectRow {item} />
        {/each}
      </ul>
    {/snippet}
  </Async>
</div>
