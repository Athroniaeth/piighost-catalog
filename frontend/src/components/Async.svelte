<script lang="ts" generics="T">
  import type { Snippet } from "svelte";
  import Loader from "@lucide/svelte/icons/loader-circle";
  import Button from "./ui/Button.svelte";
  import { t } from "../lib/i18n.svelte";
  import { ApiError } from "../lib/api";

  /**
   * Render a promise: spinner, error with retry, or the content. A page that
   * names something the API does not know passes `notfound`: a 404 then draws
   * that page, since retrying cannot make the object exist.
   */
  let {
    promise,
    children,
    onretry = null,
    notfound,
  }: {
    promise: Promise<T>;
    children: Snippet<[T]>;
    onretry?: (() => void) | null;
    notfound?: Snippet;
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
  {#if notfound && error instanceof ApiError && error.status === 404}
    {@render notfound()}
  {:else}
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
  {/if}
{/await}
