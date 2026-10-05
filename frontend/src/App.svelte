<script lang="ts">
  import SiteFooter from "./components/SiteFooter.svelte";
  import SiteNav from "./components/SiteNav.svelte";
  import Chat from "./routes/Chat.svelte";
  import Configs from "./routes/Configs.svelte";
  import Compare from "./routes/Compare.svelte";
  import Contribute from "./routes/Contribute.svelte";
  import Detail from "./routes/Detail.svelte";
  import Home from "./routes/Home.svelte";
  import Labels from "./routes/Labels.svelte";
  import NotFound from "./routes/NotFound.svelte";
  import Playground from "./routes/Playground.svelte";
  import Stats from "./routes/Stats.svelte";
  import { i18n, t, type Key } from "./lib/i18n.svelte";
  import { interceptLinks, router } from "./lib/router.svelte";

  const route = $derived(router.route);

  // One title per route. Without this every tab, every bookmark and every
  // shared link read "piighost catalog", which is useless once you have three of
  // them open. The reference is the title on a detail page, since that is what
  // someone is actually pointing at.
  const title = $derived.by(() => {
    const suffix = t("home.title");
    if (route.name === "home") return suffix;
    if (route.name === "detail")
      return `${route.params.namespace}/${route.params.name} · ${suffix}`;
    const heading: Record<string, Key> = {
      labels: "labels.title",
      stats: "stats.title",
      configs: "configs.title",
      playground: "nav.playground",
      compare: "play.compare",
      chat: "play.chat",
      contribute: "nav.contribute",
    };
    const key = heading[route.name] ?? "common.notFound";
    return `${t(key)} · ${suffix}`;
  });

  // The document language follows the switcher: a screen reader picks its voice
  // from it, and it is the one piece of the page Svelte does not own.
  $effect(() => {
    document.documentElement.lang = i18n.locale;
  });

  $effect(() => {
    document.title = title;
  });
</script>

<svelte:body onclick={interceptLinks} />

<a class="skip-link" href="#content">{t("nav.skip")}</a>

<div class="flex min-h-dvh flex-col">
  <SiteNav />
  <main id="content" class="flex-1">
    {#if route.name === "home"}
      <Home />
    {:else if route.name === "labels"}
      <Labels />
    {:else if route.name === "stats"}
      <Stats />
    {:else if route.name === "configs"}
      <Configs />
    {:else if route.name === "playground"}
      <Playground />
    {:else if route.name === "compare"}
      <Compare />
      <!-- Unreachable while CHAT_ENABLED is false; kept so the flag is the
           only thing to flip when a model detector lands. -->
    {:else if route.name === "chat"}
      <Chat />
    {:else if route.name === "contribute"}
      <Contribute />
    {:else if route.name === "detail"}
      {#key router.path}
        <Detail
          namespace={route.params.namespace}
          name={route.params.name}
          selector={route.params.selector ?? "latest"}
        />
      {/key}
    {:else}
      <NotFound />
    {/if}
  </main>
  <SiteFooter />
</div>
