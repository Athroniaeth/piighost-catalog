<script lang="ts">
  import Async from "../components/Async.svelte";
  import Sparkbars from "../components/Sparkbars.svelte";
  import StatBars from "../components/StatBars.svelte";
  import Card from "../components/ui/Card.svelte";
  import Segmented from "../components/ui/Segmented.svelte";
  import { api } from "../lib/api";
  import { plural, t } from "../lib/i18n.svelte";
  import { refPath } from "../lib/router.svelte";

  let days = $state("30");

  const stats = $derived(api.stats(Number(days)));

  const windows = $derived([
    { value: "7", label: t("stats.7") },
    { value: "30", label: t("stats.30") },
    { value: "90", label: t("stats.90") },
  ]);
</script>

<div class="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-8">
  <div class="flex flex-wrap items-baseline gap-x-3">
    <h1 class="text-xl font-semibold tracking-tight">{t("stats.title")}</h1>
    <p class="text-sm text-muted-foreground">{t("stats.lede")}</p>
  </div>

  <Segmented options={windows} bind:value={days} label={t("stats.window")} />

  <Async promise={stats}>
    {#snippet children(report)}
      <div class="grid gap-3 sm:grid-cols-3">
        {#each [["pipelinesPulled", report.pulls], ["objectsBrowsed", report.browses], ["searches", report.searches]] as const as [key, value] (key)}
          <div class="rounded-xl border bg-card p-4">
            <p class="text-2xl font-semibold tabular-nums">{value}</p>
            <p class="mt-0.5 text-sm text-muted-foreground">
              {plural(key, value)}
            </p>
          </div>
        {/each}
      </div>

      <Card title={t("stats.perDay")}>
        <Sparkbars rows={report.per_day} label={t("stats.perDay")} />
        <p class="mt-2 flex justify-between text-xs text-muted-foreground">
          <span>{report.per_day.at(0)?.key}</span>
          <span>{report.per_day.at(-1)?.key}</span>
        </p>
      </Card>

      <div class="grid gap-3 lg:grid-cols-2">
        <Card title={t("stats.top")}>
          <StatBars rows={report.top_objects} href={refPath} />
        </Card>
        <div class="flex flex-col gap-3">
          <Card title={t("stats.selectors")}>
            <StatBars rows={report.selectors} />
            <p class="mt-2 text-xs text-muted-foreground">
              {t("stats.selectorsNote")}
            </p>
          </Card>
          <Card title={t("stats.clients")}>
            <StatBars rows={report.clients} />
          </Card>
        </div>
      </div>

      <p class="text-xs text-muted-foreground">{t("stats.privacy")}</p>
    {/snippet}
  </Async>
</div>
