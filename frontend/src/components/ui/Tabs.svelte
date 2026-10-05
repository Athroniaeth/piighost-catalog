<script lang="ts">
  import { cn } from "../../lib/cn";
  import { localize, router } from "../../lib/router.svelte";

  /**
   * Link tabs between sibling pages, the studio's PlaygroundTabs pattern. The
   * hrefs are written without the language, which is added here.
   */
  let {
    tabs,
    label,
  }: { tabs: { href: string; label: string }[]; label: string } = $props();

  const current = $derived(router.local.replace(/\/+$/, "") || "/");
</script>

<nav
  aria-label={label}
  class="mb-3 flex shrink-0 gap-1 self-start rounded-lg border bg-muted/40 p-1 text-sm"
>
  {#each tabs as tab (tab.href)}
    {@const active = current === tab.href}
    <a
      href={localize(tab.href)}
      aria-current={active ? "page" : undefined}
      class={cn(
        "rounded-md px-3 py-1.5 font-medium transition-colors",
        active
          ? "bg-background text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {tab.label}
    </a>
  {/each}
</nav>
