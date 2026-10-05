<script lang="ts">
  import { tick } from "svelte";
  import ChevronDown from "@lucide/svelte/icons/chevron-down";
  import Search from "@lucide/svelte/icons/search";
  import type { SearchHit, SearchOut } from "../generated/api";
  import { api } from "../lib/api";
  import { cn } from "../lib/cn";
  import { plural, t, type Key } from "../lib/i18n.svelte";
  import KindIcon from "./KindIcon.svelte";

  /**
   * The object picker for the playground, the chat and the contribution forms.
   *
   * A native select gave 218 lines of identical grey text, which told a visitor
   * neither what an entry was nor how much it covered. This one leads with the
   * groups, since a group is the set of regexes someone came to run, and
   * carries the kind as a glyph and the coverage as a number.
   *
   * The panel is a popover, in the browser's top layer, and that is not a
   * detail. Every screen that uses this picker sits in a card that clips to
   * draw its rounded corners, and the source rows of a group sit in a scroller
   * on top of that. An absolutely positioned panel was cut by whichever
   * ancestor came first, which is how a list of two hundred objects arrived as
   * a sliver showing its filter field and nothing else. The top layer is
   * outside all of them.
   *
   * Position therefore has to be computed, and it is set through the CSSOM
   * rather than a `style` attribute in markup. The production CSP allows
   * `style-src 'self'` with no `unsafe-inline`, and CSSOM assignment is not
   * what that forbids; verified against the deployed headers.
   */
  let {
    value = $bindable(),
    kinds = null,
    id,
    label,
  }: {
    value: string;
    /**
     * Which kinds may be chosen, or null for every one.
     *
     * A list rather than one kind, because the question a caller asks is not
     * always about a single kind: a group's sources are patterns *or* groups,
     * and a configuration is neither. Offering one anyway is how a visitor
     * picks something the resolver then refuses, which is what happened.
     */
    kinds?: Kind[] | null;
    id: string;
    label: string;
  } = $props();

  type Kind = "pattern" | "group" | "config";

  // Groups first, then patterns, then configurations. The catalog is a registry of
  // regexes: a group is a set of them you can run as it is, a pattern is one
  // shape, and a configuration is a piighost pipeline that happens to carry
  // regexes — a different object, and not what someone came here for. Within
  // a kind the widest coverage leads.
  const RANK: Record<string, number> = { group: 0, pattern: 1, config: 2 };

  /** Wide enough for the longest key, unless the trigger is wider still. */
  const MIN_WIDTH = 320;
  const MARGIN = 8;

  let open = $state(false);
  let filter = $state("");
  let trigger = $state<HTMLButtonElement | null>(null);
  let panel = $state<HTMLDivElement | null>(null);
  let field = $state<HTMLInputElement | null>(null);
  let list = $state<HTMLDivElement | null>(null);

  const options = $derived(api.search({}));
  const needle = $derived(filter.trim().toLowerCase());

  function ordered(result: SearchOut): SearchHit[] {
    const allowed = kinds
      ? result.items.filter((item) => kinds.includes(item.kind as Kind))
      : result.items;
    return [...allowed].sort(
      (a, b) =>
        RANK[a.kind] - RANK[b.kind] ||
        b.labels.length - a.labels.length ||
        a.key.localeCompare(b.key),
    );
  }

  function matching(items: SearchHit[]): SearchHit[] {
    if (needle === "") return items;
    return items.filter(
      (item) =>
        item.key.toLowerCase().includes(needle) ||
        item.tags.some((tag) => tag.includes(needle)) ||
        item.labels.some((entry) => entry.toLowerCase().includes(needle)),
    );
  }

  /** The whole key and what the bare number means, for the title on hover. */
  function countLabel(item: SearchHit): string {
    const kindName = t(`kind.${item.kind}` as Key);
    return `${item.key} • ${kindName} • ${item.labels.length} ${plural("coverage", item.labels.length)}`;
  }

  /** Put the panel under its trigger, or above it when the room is below. */
  function place() {
    if (!trigger || !panel) return;
    const anchor = trigger.getBoundingClientRect();
    const width = Math.min(
      Math.max(anchor.width, MIN_WIDTH),
      window.innerWidth - 2 * MARGIN,
    );
    panel.style.width = `${width}px`;

    // Decide the side first, then cap to that side's room. Capping to the
    // larger of the two and then placing below is how a panel ends up hanging
    // past the bottom of a short window.
    const below = window.innerHeight - anchor.bottom - MARGIN;
    const above = anchor.top - MARGIN;

    // Lifting the cap to measure the natural height un-overflows the listbox
    // for one layout pass, and the browser clamps its scrollTop to the zero it
    // sees. Carry the position across the measurement.
    const keep = list?.scrollTop ?? 0;
    panel.style.maxHeight = "none";
    const natural = panel.offsetHeight;
    const underneath = natural <= below || below >= above;
    const room = underneath ? below : above;
    panel.style.maxHeight = `${Math.round(room)}px`;
    if (list) list.scrollTop = keep;

    const height = Math.min(natural, room);
    const top = underneath ? anchor.bottom + 4 : anchor.top - height - 4;
    const left = Math.min(
      Math.max(MARGIN, anchor.left),
      window.innerWidth - width - MARGIN,
    );
    panel.style.top = `${Math.round(top)}px`;
    panel.style.left = `${Math.round(left)}px`;
  }

  async function show() {
    // The panel element is always in the tree, because `showPopover` needs
    // something to call; its contents are not, because two hundred options per
    // picker, times one per detector row, is a lot of DOM for a list nobody has
    // opened.
    panel?.showPopover();
    await tick();
    place();
    field?.focus();
  }

  function hide() {
    panel?.hidePopover();
  }

  function choose(key: string) {
    value = key;
    hide();
  }

  /** Light dismiss and Escape close it without going through `hide`. */
  function ontoggle(event: Event) {
    open = (event as ToggleEvent).newState === "open";
    if (!open) filter = "";
  }

  function onkeydown(event: KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) show();
      else panel?.querySelector<HTMLButtonElement>('[role="option"]')?.focus();
    }
  }

  // A popover in the top layer does not move with the page, so it has to be
  // told. Scrolling a source row out from under its own panel would otherwise
  // leave the panel behind.
  //
  // The listener captures, because the scroller that moves the trigger is an
  // ancestor and its scroll does not bubble. Capturing also catches the
  // listbox's own scroll, which must be ignored: repositioning on it fought
  // every wheel tick and the list read as stuck.
  $effect(() => {
    if (!open) return;
    const reposition = (event: Event) => {
      const target = event.target;
      if (target instanceof Node && panel?.contains(target)) return;
      place();
    };
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  });
</script>

{#await options then result}
  {@const items = ordered(result)}
  {@const current = items.find((item) => item.key === value)}
  <button
    {id}
    bind:this={trigger}
    type="button"
    aria-label={label}
    aria-expanded={open}
    aria-haspopup="listbox"
    class="flex h-9 w-full items-center gap-2 rounded-md border bg-background px-2 text-left text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
    onclick={() => (open ? hide() : show())}
    {onkeydown}
  >
    <KindIcon
      kind={current?.kind ?? "config"}
      class="size-4 shrink-0 text-muted-foreground"
    />
    <span class="min-w-0 flex-1 truncate font-mono">{value}</span>
    {#if current}
      <span
        class="shrink-0 tabular-nums text-muted-foreground"
        title={countLabel(current)}
      >
        {current.labels.length}
      </span>
    {/if}
    <ChevronDown class="size-4 shrink-0 text-muted-foreground" />
  </button>

  <div
    bind:this={panel}
    popover="auto"
    {ontoggle}
    class="fixed m-0 flex-col overflow-hidden rounded-lg border bg-card p-0 shadow-lg"
  >
    {#if open}
      <label class="relative block shrink-0 border-b">
        <Search
          class="absolute start-2 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <input
          bind:this={field}
          bind:value={filter}
          spellcheck="false"
          placeholder={t("pick.filter")}
          aria-label={t("pick.filter")}
          class="h-9 w-full bg-transparent ps-8 pe-2 text-sm outline-none"
          {onkeydown}
        />
      </label>
      <div
        bind:this={list}
        role="listbox"
        aria-label={label}
        class="min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-contain p-1"
      >
        {#each matching(items) as item (item.key)}
          <button
            type="button"
            role="option"
            aria-selected={item.key === value}
            class={cn(
              "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none",
              item.key === value
                ? "bg-muted font-medium"
                : "hover:bg-muted focus-visible:bg-muted",
            )}
            title={countLabel(item)}
            onclick={() => choose(item.key)}
            {onkeydown}
          >
            <KindIcon
              kind={item.kind}
              class="size-4 shrink-0 text-muted-foreground"
            />
            <span class="min-w-0 flex-1 truncate font-mono">{item.key}</span>
            <span class="shrink-0 text-xs tabular-nums text-muted-foreground">
              {item.labels.length}
            </span>
          </button>
        {:else}
          <p class="px-2 py-3 text-sm text-muted-foreground">
            {t("pick.none")}
          </p>
        {/each}
      </div>
    {/if}
  </div>
{/await}
