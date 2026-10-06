<script lang="ts">
  import Download from "@lucide/svelte/icons/download";
  import GitCommit from "@lucide/svelte/icons/git-commit-horizontal";
  import Play from "@lucide/svelte/icons/play";
  import FileCog from "@lucide/svelte/icons/file-cog";
  import type { CommitDetail, ObjectDetail, Resolved } from "../generated/api";
  import Async from "../components/Async.svelte";
  import EntityLabel from "../components/EntityLabel.svelte";
  import EntityRow from "../components/EntityRow.svelte";
  import KindIcon from "../components/KindIcon.svelte";
  import BrandIcon from "../components/BrandIcon.svelte";
  import DataText from "../components/DataText.svelte";
  import Badge from "../components/ui/Badge.svelte";
  import Button from "../components/ui/Button.svelte";
  import Card from "../components/ui/Card.svelte";
  import CodeBlock from "../components/ui/CodeBlock.svelte";
  import CopyButton from "../components/ui/CopyButton.svelte";
  import Segmented from "../components/ui/Segmented.svelte";
  import { track } from "../lib/analytics";
  import { ApiError, api, download } from "../lib/api";
  import { cn } from "../lib/cn";
  import { segments } from "../lib/highlight";
  import { i18n, plural, t } from "../lib/i18n.svelte";
  import { assignLabelColors, labelStyle } from "../lib/labels";
  import { localize, refPath, router } from "../lib/router.svelte";
  import { relativeTime } from "../lib/time";
  import { FIELD } from "../lib/ui";
  import NotFound from "./NotFound.svelte";

  let {
    namespace,
    name,
    selector = "latest",
  }: { namespace: string; name: string; selector?: string } = $props();

  type Tab = "content" | "pipeline";

  const ref = $derived({ namespace, name, selector });

  const bundle = $derived(
    (async () => {
      const [object, commit, resolved] = await Promise.all([
        api.object(namespace, name),
        api.commit(ref),
        api.resolved(ref),
      ]);
      return { object, commit, resolved };
    })(),
  );

  // A secondary load: a failure must not blank the page.
  const snippets = $derived(api.snippets(ref).catch(() => null));

  let tab = $state<Tab>("content");
  // By catalog id first: naming the reference is the short form and the one that
  // keeps the patterns auditable at their source. Inlining is the fallback,
  // for a file that has to work with no catalog to reach.
  let form = $state<"flattened" | "referenced">("referenced");
  let memory = $state<"" | "in_memory" | "redis" | "sqlalchemy">("");
  let snippet = $state("python");
  // A config chooses a linker, an anonymizer, sometimes a guard and a memory,
  // which are decisions about the application rather than about detection.
  // Taking the detector alone is how you keep the registry's half.
  let part = $state<"pipeline" | "detector">("pipeline");

  const pipeline = $derived(
    api
      .pipeline(ref, {
        memory: part === "detector" ? undefined : memory || undefined,
        keepRefs: form === "referenced",
        part,
      })
      .catch(
        (caught: unknown) =>
          `# ${caught instanceof ApiError ? caught.message : caught}`,
      ),
  );

  const tabs = $derived<{ value: Tab; label: string }[]>([
    { value: "content", label: t("detail.content") },
    { value: "pipeline", label: t("detail.pipeline") },
  ]);
  const formOptions = $derived([
    { value: "referenced" as const, label: t("detail.referenced") },
    { value: "flattened" as const, label: t("detail.flattened") },
  ]);
  const partOptions = $derived([
    { value: "pipeline" as const, label: t("detail.wholePipeline") },
    { value: "detector" as const, label: t("detail.detectorOnly") },
  ]);

  async function savePipeline() {
    const suffix = part === "detector" ? "detector" : "pipeline";
    download(`${name}-${suffix}.toml`, await pipeline, "application/toml");
    // Which rendering people take away is the question `keep_refs` exists to
    // answer: a flattened file works offline, a referenced one needs the catalog.
    track({
      name: "pipeline_copied",
      props: { form, memory: memory || "none", part },
    });
  }

  function exampleParts(text: string, value: string, label: string) {
    const start = text.indexOf(value);
    if (start < 0) return segments(text, []);
    return segments(text, [
      {
        start,
        end: start + value.length,
        label,
        kept: true,
        detector: "",
        pattern: null,
      },
    ]);
  }

  function kindName(kind: string) {
    return kind === "pattern"
      ? t("kind.pattern")
      : kind === "group"
        ? t("kind.group")
        : t("kind.config");
  }

  /** Tags pointing at a given commit, `latest` included. */
  function pointersOf(object: ObjectDetail, commit: string) {
    return Object.entries(object.pointers)
      .filter(([, at]) => at === commit)
      .map(([tag]) => tag);
  }
</script>

<Async promise={bundle} onretry={() => router.go(router.path)}>
  {#snippet notfound()}
    <NotFound />
  {/snippet}
  {#snippet children({
    object,
    commit,
    resolved,
  }: {
    object: ObjectDetail;
    commit: CommitDetail;
    resolved: Resolved;
  })}
    {@const colors = assignLabelColors(
      resolved.labels?.map((e) => e.label) ??
        resolved.detectors?.flatMap(
          (d) => d.labels?.map((e) => e.label) ?? [],
        ) ??
        [],
    )}
    <div class="border-b">
      <div
        class="mx-auto flex max-w-7xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-4"
      >
        <KindIcon kind={object.kind} class="size-5 text-muted-foreground" />
        <h1 class="font-mono text-xl font-bold tracking-tight">
          <!-- The namespace links to its objects, as the header's trail did
               before the shared header replaced it. -->
          <a
            href={localize(`/?q=${encodeURIComponent(object.namespace)}`)}
            class="text-muted-foreground hover:text-foreground hover:underline"
            >{object.namespace}</a
          ><span class="text-muted-foreground">/</span>{object.name}
        </h1>
        <Badge variant="outline">{kindName(object.kind)}</Badge>
        {#each object.tags as tag (tag)}
          <Badge
            variant="secondary"
            href={localize(`/?tag=${encodeURIComponent(tag)}`)}>{tag}</Badge
          >
        {/each}
        <div class="no-print ms-auto flex items-center gap-1.5">
          <CopyButton
            value="{object.key}:{commit.commit}"
            class="ring-1 ring-foreground/10"
          />
          <Button
            variant="outline"
            size="icon"
            aria-label={t("detail.download")}
            onclick={savePipeline}
          >
            <Download />
          </Button>
          <Button
            href={localize(`/playground?ref=${encodeURIComponent(object.key)}`)}
          >
            <Play />
            {t("detail.tryIt")}
          </Button>
        </div>
      </div>
      <p class="mx-auto max-w-7xl px-4 pb-4 text-sm text-muted-foreground">
        <DataText text={object.description} />
      </p>
    </div>

    <div
      class="mx-auto grid max-w-7xl gap-8 px-4 py-6 lg:grid-cols-[17rem_minmax(0,1fr)]"
    >
      <aside class="no-print">
        <h2 class="mb-3 text-sm font-medium">
          {t("detail.history")}
          <span class="ms-1 text-muted-foreground tabular-nums"
            >{object.commits.length}</span
          >
        </h2>
        <ol class="space-y-2">
          {#each object.commits as entry (entry.commit)}
            {@const selected = entry.commit === commit.commit}
            <li>
              <a
                href={refPath(`${object.key}:${entry.commit}`)}
                aria-current={selected ? "true" : undefined}
                class={cn(
                  "block rounded-lg p-3 ring-1 ring-foreground/10 transition-colors hover:bg-muted/60",
                  selected && "bg-muted",
                )}
              >
                <span
                  class="flex items-center gap-2 font-mono text-sm font-medium"
                >
                  <GitCommit
                    class="size-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  {entry.commit}
                  {#each pointersOf(object, entry.commit) as pointer (pointer)}
                    <Badge
                      variant={pointer === "latest" ? "outline" : "default"}
                      class="font-mono">{pointer}</Badge
                    >
                  {/each}
                </span>
                <span class="mt-1 block ps-6 text-xs text-muted-foreground">
                  {relativeTime(entry.recorded_at, i18n.locale) ??
                    t("detail.unrecorded")}
                </span>
              </a>
            </li>
          {/each}
        </ol>
      </aside>

      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <GitCommit class="size-5 text-muted-foreground" aria-hidden="true" />
          <h2 class="font-mono text-lg font-semibold">{commit.commit}</h2>
          {#each pointersOf(object, commit.commit) as pointer (pointer)}
            <Badge
              variant={pointer === "latest" ? "outline" : "default"}
              class="font-mono">{pointer}</Badge
            >
          {/each}
          <span class="text-xs text-muted-foreground"
            >{relativeTime(commit.recorded_at, i18n.locale) ??
              t("detail.unrecorded")}</span
          >
          {#if object.pulls > 0}
            <span
              class="inline-flex items-center gap-1 text-xs text-primary"
              title={t("detail.pullsWindow")}
            >
              <Download class="size-3.5" />
              {object.pulls}
              {plural("pulls", object.pulls)}
            </span>
          {/if}
        </div>

        <div role="tablist" class="no-print mt-4 flex flex-wrap gap-1">
          {#each tabs as item (item.value)}
            <button
              type="button"
              role="tab"
              aria-selected={tab === item.value}
              class={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                tab === item.value
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onclick={() => (tab = item.value)}
            >
              {item.label}
            </button>
          {/each}
        </div>

        <div class="mt-5 flex flex-col gap-5">
          {#if tab === "content"}
            {#if object.kind === "pattern"}
              <Card title={t("detail.pattern")} bodyClass="space-y-2">
                <CodeBlock
                  code={String(commit.content.regex)}
                  language="regex"
                  wrap
                />
                <p class="text-xs text-muted-foreground">
                  {t("detail.engine")} · <EntityLabel
                    label={String(commit.content.label)}
                    {colors}
                  />
                </p>
              </Card>
              {#if commit.content.examples}
                {@const examples = commit.content.examples as {
                  match: { text: string; value: string }[];
                  no_match: { text: string }[];
                }}
                <div class="grid gap-5 sm:grid-cols-2">
                  <Card title={t("detail.matches")}>
                    <ul class="space-y-1.5">
                      {#each examples.match as example, index (index)}
                        <!-- A secret is one unbroken token, a JWT runs past a
                             hundred characters: it wraps anywhere rather than
                             widening the card past the window. -->
                        <li
                          class="rounded-md bg-muted/40 p-2 font-mono text-sm leading-relaxed [overflow-wrap:anywhere]"
                        >
                          {#each exampleParts(example.text, example.value, String(commit.content.label)) as part, i (i)}{#if part.hit}<span
                                class="rounded px-1 [box-decoration-break:clone] {labelStyle(
                                  part.hit.label,
                                  colors,
                                )}">{part.text}</span
                              >{:else}{part.text}{/if}{/each}
                        </li>
                      {/each}
                    </ul>
                  </Card>
                  <Card title={t("detail.noMatches")}>
                    <ul class="space-y-1.5">
                      {#each examples.no_match as example, index (index)}
                        <li
                          class="rounded-md bg-muted/40 p-2 font-mono text-sm text-muted-foreground [overflow-wrap:anywhere]"
                        >
                          {example.text}
                        </li>
                      {/each}
                    </ul>
                  </Card>
                </div>
              {/if}
            {/if}

            {#if object.kind === "group" && Array.isArray(commit.content.sources)}
              <Card title={t("detail.sources")} bodyClass="space-y-2">
                <ol class="space-y-1.5">
                  {#each commit.content.sources as source, index (index)}
                    {@const entry = source as {
                      ref: string;
                      commit: string;
                      exclude: string[];
                      only: string[];
                    }}
                    <li
                      class="flex flex-wrap items-center gap-2 rounded-md bg-muted/40 p-2 text-sm"
                    >
                      <span
                        class="grid size-5 place-items-center rounded-full bg-primary/10 font-mono text-xs font-semibold text-primary tabular-nums"
                        >{index + 1}</span
                      >
                      <a
                        class="font-mono hover:underline"
                        href={refPath(entry.ref)}>{entry.ref}</a
                      >
                      <span class="font-mono text-xs text-muted-foreground"
                        >:{entry.commit}</span
                      >
                      {#if entry.exclude.length > 0}<span
                          class="text-xs text-muted-foreground"
                          >{t("detail.excluded")}
                          {entry.exclude.join(", ")}</span
                        >{/if}
                      {#if entry.only.length > 0}<span
                          class="text-xs text-muted-foreground"
                          >{t("detail.only")} {entry.only.join(", ")}</span
                        >{/if}
                    </li>
                  {/each}
                </ol>
                <p class="text-xs text-muted-foreground">
                  {t("detail.sourcesNote")}
                </p>
              </Card>
            {/if}

            <!-- Use it leads, and the stages a config chose - linker,
                 anonymizer, memory - used to be what sat here instead. Those
                 are the application's choices, not the registry's. What the
                 object is made of comes after how to run it, because a
                 visitor arrives wanting the second; the Pipeline file tab
                 still shows the whole thing for whoever wants the stages too.
                 -->
            <Async promise={snippets}>
              {#snippet children(value)}
                {#if value}
                  <Card title={t("detail.use")} bodyClass="space-y-3">
                    {#snippet action()}
                      <Segmented
                        options={Object.keys(value.items).map((k) => ({
                          value: k,
                          label: k,
                        }))}
                        bind:value={snippet}
                        label={t("detail.use")}
                        size="default"
                      >
                        {#snippet icon(name)}
                          {#if name === "python"}
                            <BrandIcon name="python" />
                          {:else}
                            <FileCog class="size-4 shrink-0" />
                          {/if}
                        {/snippet}
                      </Segmented>
                    {/snippet}
                    <CodeBlock
                      code={value.items[snippet] ??
                        Object.values(value.items)[0]}
                      language={snippet === "python" ? "python" : "toml"}
                    />
                  </Card>
                {/if}
              {/snippet}
            </Async>

            {#if resolved.detectors}
              <Card title={t("detail.detectors")}>
                <ol class="space-y-2">
                  {#each resolved.detectors as detector (detector.name)}
                    <li class="rounded-md bg-muted/40 p-3">
                      <div class="flex flex-wrap items-baseline gap-2">
                        <span class="font-medium">{detector.name}</span>
                        <span class="font-mono text-xs text-muted-foreground"
                          >{detector.type}</span
                        >
                        {#each detector.groups as group (group)}
                          <a
                            class="font-mono text-xs hover:underline"
                            href={refPath(group)}>{group}</a
                          >
                        {/each}
                      </div>
                      {#if detector.labels}
                        <p class="mt-2 flex flex-wrap gap-1">
                          {#each detector.labels as entry (entry.label)}<EntityLabel
                              label={entry.label}
                              {colors}
                            />{/each}
                        </p>
                      {/if}
                    </li>
                  {/each}
                </ol>
              </Card>
            {/if}

            {#if resolved.labels && object.kind !== "pattern"}
              <Card title={t("detail.labels")}>
                <ul class="space-y-1.5">
                  {#each resolved.labels as entry (entry.label)}
                    <EntityRow label={entry.label} text={entry.regex} {colors}>
                      {#snippet trailing()}
                        <a
                          href={refPath(entry.pattern)}
                          class="font-mono hover:underline"
                          >{entry.pattern.split("/").pop()?.split(":")[0]}</a
                        >
                      {/snippet}
                    </EntityRow>
                  {/each}
                </ul>
              </Card>
            {/if}
          {:else if tab === "pipeline"}
            <Card title={t("detail.pipeline")} bodyClass="space-y-3">
              {#snippet action()}
                <Segmented
                  options={formOptions}
                  bind:value={form}
                  label={t("detail.pipeline")}
                />
              {/snippet}
              <div
                class="no-print flex flex-wrap items-center gap-3 text-xs text-muted-foreground"
              >
                <Segmented
                  options={partOptions}
                  bind:value={part}
                  label={t("detail.part")}
                />
                {#if part === "pipeline"}
                  <label class="flex items-center gap-2">
                    {t("detail.memory")}
                    <select bind:value={memory} class="{FIELD} w-auto">
                      <option value="">{t("detail.none")}</option>
                      <option value="in_memory">in_memory</option>
                      <option value="redis">redis</option>
                      <option value="sqlalchemy">sqlalchemy</option>
                    </select>
                  </label>
                {:else}
                  <p class="max-w-md">{t("detail.detectorNote")}</p>
                {/if}
                <Button
                  variant="outline"
                  size="sm"
                  class="ms-auto"
                  onclick={savePipeline}
                  ><Download />{t("detail.download")}</Button
                >
              </div>
              {#await pipeline then body}
                <CodeBlock code={body} language="toml" />
              {/await}
            </Card>
          {/if}
        </div>
      </div>
    </div>
  {/snippet}
</Async>
