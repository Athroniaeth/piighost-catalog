<script lang="ts" generics="T">
  import type { Snippet } from "svelte";
  import Loader from "@lucide/svelte/icons/loader-circle";
  import Button from "./ui/Button.svelte";
  import { t } from "../lib/i18n.svelte";

  /** Render a promise: spinner, error with retry, or the content. */
  let {
    promise,
    children,
    onretry = null,
  }: {
    promise: Promise<T>;
    children: Snippet<[T]>;
    onretry?: (() => void) | null;
  } = $props();
</script>

{#await promise}
  <p
    class="flex items-center gap-2 py-8 text-sm text-muted-foreground"
    role="status"
  >
    <Loader class="size-4 animate-spin" aria-hidden="true" />
    {t("common.loading")}
  </p>
{:then value}
  {@render children(value)}
{:catch error}
  <div class="rounded-lg border bg-muted/30 p-4 text-sm" role="alert">
    <p class="text-destructive">
      {t("common.error")}{t("common.colon")}
      {error.message}
    </p>
    {#if onretry}
      <Button variant="outline" size="sm" class="mt-3" onclick={onretry}
        >{t("common.retry")}</Button
      >
    {/if}
  </div>
{/await}
