<script lang="ts">
  import type { Snippet } from "svelte";
  import Tabs from "./ui/Tabs.svelte";
  import { t } from "../lib/i18n.svelte";
  import { CHAT_ENABLED } from "../lib/router.svelte";

  /**
   * The studio's workshop shell: full height under the 4rem header, link tabs
   * between the modes, then one card divided into numbered regions.
   */
  let { children }: { children: Snippet } = $props();

  const tabs = $derived([
    { href: "/playground", label: t("play.run") },
    { href: "/playground/compare", label: t("play.compare") },
    ...(CHAT_ENABLED
      ? [{ href: "/playground/chat", label: t("play.chat") }]
      : []),
  ]);
</script>

<div
  class="mx-auto flex w-full max-w-[88rem] flex-col p-4 lg:h-[calc(100dvh-4rem)]"
>
  <!-- The page's heading, beside the tabs so the full-height card keeps its
       room: "Playground" is the page, Run and Compare are its modes. -->
  <div class="mb-3 flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2">
    <h1 class="text-xl font-semibold tracking-tight">
      {t("nav.playground")}
    </h1>
    <Tabs {tabs} label={t("nav.playground")} />
  </div>
  <div
    class="grid flex-1 divide-y overflow-hidden rounded-xl border bg-card shadow-sm lg:min-h-0 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.9fr)_minmax(0,1.05fr)] lg:divide-x lg:divide-y-0"
  >
    {@render children()}
  </div>
</div>
