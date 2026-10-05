<script lang="ts">
  import Logo from "./Logo.svelte";
  import { cn } from "../lib/cn";

  /**
   * The name, once, so the nav and the hero cannot drift apart.
   *
   * Not translated and not a dictionary key: a product name is the same in
   * every language, and `catalog` carries the accent colour the way it does
   * everywhere else on the site. Set like the piighost wordmark (charter v3):
   * Schibsted Grotesk 700, tracking -0.035em, always lowercase. The mark sizes
   * itself in `em`, so the caller only sets a font size.
   */
  let { class: extra = "" }: { class?: string } = $props();
</script>

<span
  class={cn(
    "inline-flex items-center gap-[0.3125em] font-sans font-bold tracking-[-0.035em]",
    extra,
  )}
>
  <Logo class="size-[1.17em] shrink-0" />
  <span class="inline-flex items-center gap-[0.25em]">
    <span>piighost</span>
    <span class="text-primary">catalog</span>
  </span>
</span>
