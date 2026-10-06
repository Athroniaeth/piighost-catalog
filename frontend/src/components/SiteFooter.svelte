<script lang="ts">
  import Wordmark from "./Wordmark.svelte";
  import { i18n, t } from "../lib/i18n.svelte";
  import { localize } from "../lib/router.svelte";
</script>

<footer class="border-t">
  <div class="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:grid-cols-3">
    <div>
      <p class="text-lg font-bold"><Wordmark /></p>
      <p class="mt-2 max-w-xs text-sm text-muted-foreground">
        {t("footer.tagline")}
      </p>
    </div>
    <div>
      <p class="text-sm font-semibold">piighost</p>
      <ul class="mt-3 space-y-2 text-sm text-muted-foreground">
        <li>
          <a
            class="hover:text-foreground"
            href="https://piighost.dev/{i18n.locale}">piighost.dev</a
          >
        </li>
        <li>
          <a
            class="hover:text-foreground"
            href="https://github.com/Athroniaeth/piighost"
            target="_blank"
            rel="noreferrer">GitHub</a
          >
        </li>
        <li>
          <a
            class="hover:text-foreground"
            href="https://pypi.org/project/piighost/"
            target="_blank"
            rel="noreferrer">PyPI</a
          >
        </li>
        <li>
          <a
            class="hover:text-foreground"
            href="https://docs.piighost.dev/{i18n.locale}/"
            target="_blank"
            rel="noreferrer">{t("footer.docs")}</a
          >
        </li>
        <li>
          <a
            class="hover:text-foreground"
            href="https://docs-chat.piighost.dev"
            target="_blank"
            rel="noreferrer">{t("footer.chat")}</a
          >
        </li>
      </ul>
    </div>
    <div>
      <p class="text-sm font-semibold">{t("footer.links")}</p>
      <ul class="mt-3 space-y-2 text-sm text-muted-foreground">
        <li>
          <a class="hover:text-foreground" href={localize("/labels")}
            >{t("labels.title")}</a
          >
        </li>
        <li>
          <a class="hover:text-foreground" href={localize("/configs")}
            >{t("configs.title")}</a
          >
        </li>
        <li>
          <a class="hover:text-foreground" href={localize("/stats")}
            >{t("stats.title")}</a
          >
        </li>
        <li>
          <a class="hover:text-foreground" href={localize("/contribute")}
            >{t("nav.contribute")}</a
          >
        </li>
        <li>
          <a
            class="hover:text-foreground"
            href="https://discord.gg/vFg9GHQR2s"
            target="_blank"
            rel="noreferrer">Discord</a
          >
        </li>
      </ul>
    </div>
  </div>
  <div class="border-t py-6 text-center text-xs text-muted-foreground">
    {t("footer.mit")}
  </div>
</footer>
