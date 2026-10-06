<script lang="ts">
  import { GithubIcon, LangMenu, SiteNav, ecosystemLinks } from "@piighost/ui";
  import SiteFooter from "./components/SiteFooter.svelte";
  import ThemeToggle from "./components/ThemeToggle.svelte";
  import Button from "./components/ui/Button.svelte";
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
  import { syncHead } from "./lib/head";
  import { i18n, t, type Key } from "./lib/i18n.svelte";
  import { interceptLinks, localize, router } from "./lib/router.svelte";

  const route = $derived(router.route);

  /**
   * The header every piighost surface shares, its middle the ecosystem menu
   * with the catalog marked. The catalog's own entry stays on this site, a
   * relative route the router handles, whatever host serves it.
   */
  const links = $derived(
    ecosystemLinks("catalog", i18n.locale).map((link) =>
      link.current ? { ...link, href: localize("/") } : link,
    ),
  );

  /** Each language links to this same page in it, query kept. */
  const locales = $derived([
    { code: "fr" as const, name: "Français", href: router.alternate("fr") },
    { code: "en" as const, name: "English", href: router.alternate("en") },
  ]);

  // One title per route. Without this every tab, every bookmark and every
  // shared link read "piighost catalog", which is useless once you have three of
  // them open.
  // The reference is no longer the title on a detail page: Detail.svelte
  // writes the object's readable name once it has loaded it, the same words
  // the prerendered page carries.
  const title = $derived.by(() => {
    const suffix = t("home.title");
    if (route.name === "home") return suffix;
    if (route.name === "detail") return null;
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

  // The document language follows the path: a screen reader picks its voice
  // from it, and a crawler that renders the page reads the alternates.
  $effect(() => {
    syncHead(i18n.locale, router.local);
  });

  $effect(() => {
    if (title) document.title = title;
  });
</script>

<svelte:body onclick={interceptLinks} />

<a class="skip-link" href="#content">{t("nav.skip")}</a>

<!-- The catalog keeps its own theme button, which says whether it is pressed,
     on the ecosystem's storage key. The language menu is the library's: each
     entry is a real link to this page in that language. -->
{#snippet controls()}
  <Button
    variant="ghost"
    size="icon"
    href="https://github.com/Athroniaeth/piighost"
    target="_blank"
    rel="noreferrer"
    aria-label={t("nav.github")}
  >
    <GithubIcon class="size-5" />
  </Button>
  <ThemeToggle />
{/snippet}

{#snippet language()}
  <LangMenu current={i18n.locale} label={t("nav.language")} {locales} />
{/snippet}

<div class="flex min-h-dvh flex-col">
  <SiteNav
    homeHref={localize("/")}
    surface="catalog"
    {links}
    mainNavigationLabel={t("nav.main")}
    menuLabel={t("nav.menu")}
  >
    {#snippet actions()}
      <!-- A wrapper carries the breakpoint: Button always sets inline-flex. -->
      <span class="me-1 hidden sm:inline-flex">
        <Button variant="outline" size="sm" href={localize("/contribute")}
          >{t("nav.contribute")}</Button
        >
      </span>
      <span class="hidden items-center gap-1 lg:flex"
        >{@render controls()}{@render language()}</span
      >
    {/snippet}
    <!-- In the phone menu the language comes first: its list opens rightwards
         from where it sits, and at the far end of the row it ran off the
         screen. It also opens upwards: the menu scrolls, and a list below its
         last row was cut by the menu's own edge. Contribute, which the bar
         hides below 640px, goes last. -->
    {#snippet menuActions()}
      <span
        class="inline-flex [&_details>ul]:bottom-full [&_details>ul]:mt-0 [&_details>ul]:mb-1.5"
        >{@render language()}</span
      >
      {@render controls()}
      <span class="ms-auto inline-flex sm:hidden">
        <Button variant="outline" href={localize("/contribute")}
          >{t("nav.contribute")}</Button
        >
      </span>
    {/snippet}
  </SiteNav>
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
      {#key router.local}
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
