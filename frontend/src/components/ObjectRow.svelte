<script lang="ts">
  import Download from "@lucide/svelte/icons/download";
  import GitCommit from "@lucide/svelte/icons/git-commit-horizontal";
  import Link from "@lucide/svelte/icons/link";
  import Play from "@lucide/svelte/icons/play";
  import Tag from "@lucide/svelte/icons/tag";
  import type { SearchHit } from "../generated/api";
  import Badge from "./ui/Badge.svelte";
  import Button from "./ui/Button.svelte";
  import DataText from "./DataText.svelte";
  import KindIcon from "./KindIcon.svelte";
  import { i18n, plural, t } from "../lib/i18n.svelte";
  import { localize, refPath } from "../lib/router.svelte";
  import { relativeTime } from "../lib/time";

  /**
   * One row of the catalog, the LangSmith Hub card: pills on top, the
   * reference as title, one line of description, then a metadata line.
   */
  let { item }: { item: SearchHit } = $props();

  const kind = $derived(
    item.kind === "pattern"
      ? t("kind.pattern")
      : item.kind === "group"
        ? t("kind.group")
        : t("kind.config"),
  );
  const updated = $derived(relativeTime(item.updated_at, i18n.locale));
</script>

<li
  class="relative rounded-xl bg-card p-5 ring-1 ring-foreground/10 transition-shadow hover:shadow-sm"
>
  <div class="flex flex-wrap items-center gap-1.5 pe-12">
    <Badge variant="outline">{kind}</Badge>
    {#each item.tags as tag (tag)}
      <Badge
        variant="secondary"
        href={localize(`/?tag=${encodeURIComponent(tag)}`)}>{tag}</Badge
      >
    {/each}
  </div>
  <Button
    variant="outline"
    size="icon"
    href={localize(`/playground?ref=${encodeURIComponent(item.key)}`)}
    aria-label={t("home.tryIt")}
    class="absolute end-4 top-4"
  >
    <Play />
  </Button>
  <h3 class="mt-3 font-mono text-lg font-semibold tracking-tight">
    <a href={refPath(item.key)} class="hover:underline">
      <span class="text-muted-foreground">{item.namespace}/</span>{item.name}
    </a>
  </h3>
  <p class="mt-1.5 line-clamp-2 text-sm text-muted-foreground">
    <DataText text={item.description} />
  </p>
  <p
    class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
  >
    <span class="inline-flex items-center gap-1"
      ><KindIcon kind={item.kind} class="size-3.5" />{kind}</span
    >
    <span aria-hidden="true">•</span>
    <span>{t("home.updated")} {updated ?? t("home.never")}</span>
    <span aria-hidden="true">•</span>
    <span class="inline-flex items-center gap-1 text-primary"
      ><Tag class="size-3.5" />{item.labels.length}
      {plural("labels", item.labels.length)}</span
    >
    <span aria-hidden="true">•</span>
    <span class="inline-flex items-center gap-1 text-primary"
      ><GitCommit class="size-3.5" />{item.commits}</span
    >
    <span aria-hidden="true">•</span>
    <span class="inline-flex items-center gap-1 text-primary"
      ><Link class="size-3.5" />{item.used_by.length}
      {plural("uses", item.used_by.length)}</span
    >
    <!-- Only once someone has: a row of zeroes is noise on a young registry. -->
    {#if item.pulls > 0}
      <span aria-hidden="true">•</span>
      <span class="inline-flex items-center gap-1 text-primary"
        ><Download class="size-3.5" />{item.pulls}
        {plural("pulls", item.pulls)}</span
      >
    {/if}
  </p>
</li>
