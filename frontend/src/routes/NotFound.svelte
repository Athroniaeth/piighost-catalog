<script lang="ts">
  import Button from "../components/ui/Button.svelte";
  import { t } from "../lib/i18n.svelte";
  import { localize } from "../lib/router.svelte";
</script>

<div class="mx-auto max-w-3xl px-4 py-24 text-center">
  <p class="font-mono text-sm text-muted-foreground">404</p>
  <h1 class="mt-2 text-2xl font-bold tracking-tight">{t("common.notFound")}</h1>
  <p class="mt-2 text-muted-foreground">{t("common.notFoundLede")}</p>
  <Button href={localize("/")} variant="outline" class="mt-6"
    >{t("common.back")}</Button
  >
</div>
