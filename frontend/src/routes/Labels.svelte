<script lang="ts">
  import Async from "../components/Async.svelte";
  import EntityLabel from "../components/EntityLabel.svelte";
  import { api } from "../lib/api";
  import { t } from "../lib/i18n.svelte";
  import { localize, refPath } from "../lib/router.svelte";

  const labels = api.labels();
</script>

<div class="mx-auto max-w-4xl px-4 py-8">
  <h1 class="text-2xl font-bold tracking-tight">{t("labels.title")}</h1>
  <p class="mt-2 max-w-2xl text-sm text-muted-foreground">{t("labels.lede")}</p>
  <Async promise={labels}>
    {#snippet children(result)}
      <ul class="mt-6 grid gap-2 sm:grid-cols-2">
        {#each result.items as entry (entry.label)}
          <li
            class="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md bg-muted/40 p-2 text-sm"
          >
            <EntityLabel
              label={entry.label}
              href={localize(`/?label=${encodeURIComponent(entry.label)}`)}
            />
            <span class="text-xs text-muted-foreground"
              >{t("labels.definedBy")}</span
            >
            {#each entry.patterns as key (key)}
              <a href={refPath(key)} class="font-mono text-xs hover:underline"
                >{key}</a
              >
            {/each}
          </li>
        {/each}
      </ul>
    {/snippet}
  </Async>
</div>
