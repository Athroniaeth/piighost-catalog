<script lang="ts">
  /**
   * The mark: piighost's ghost, identity v3, the one piighost.dev serves.
   *
   * A solid silhouette, closed eyes (^^) and a hatched drop shadow in the
   * primary colour. The silhouette and the eyes follow the mode through two
   * tokens, --marque-silhouette and --marque-yeux: the text colour and the
   * primary on dark, night violet and off-white on light. The paths are those
   * of piighost-identite/brand/outils/assembler-logo.py and of the site's
   * Ghost.svelte, so the catalog and the site cannot drift. The silhouette is never
   * the primary colour: all violet, it reads as a fingertip.
   *
   * The ids are unique per instance: the first mark on a page may sit in a
   * hidden menu, and a shared clipPath would take the others with it. Colours
   * are SVG attributes reading CSS variables, never a `style` attribute: the
   * production CSP allows `style-src 'self'` with no `unsafe-inline`.
   */
  let { class: extra = "" }: { class?: string } = $props();
  const id = $props.id();
</script>

<svg
  viewBox="0 0 32 32"
  class={extra}
  role="img"
  aria-hidden="true"
  focusable="false"
>
  <clipPath id="{id}-ombre">
    <path
      d="M8.6 27.4V14.4a10 10 0 0 1 20 0v13q-3.333 5.6-6.667 0-3.333 5.6-6.666 0-3.333 5.6-6.667 0Z"
    />
  </clipPath>
  <mask
    id="{id}-hors-corps"
    maskUnits="userSpaceOnUse"
    x="0"
    y="0"
    width="32"
    height="32"
  >
    <rect width="32" height="32" fill="white" />
    <path
      d="M5.1 24.6V11.6a10 10 0 0 1 20 0v13q-3.333 5.6-6.667 0-3.333 5.6-6.666 0-3.333 5.6-6.667 0Z"
      fill="black"
    />
  </mask>
  <g mask="url(#{id}-hors-corps)">
    <path
      clip-path="url(#{id}-ombre)"
      d="M-32.00 32L0.00 0M-28.80 32L3.20 0M-25.60 32L6.40 0M-22.40 32L9.60 0M-19.20 32L12.80 0M-16.00 32L16.00 0M-12.80 32L19.20 0M-9.60 32L22.40 0M-6.40 32L25.60 0M-3.20 32L28.80 0M-0.00 32L32.00 0M3.20 32L35.20 0M6.40 32L38.40 0M9.60 32L41.60 0M12.80 32L44.80 0M16.00 32L48.00 0M19.20 32L51.20 0M22.40 32L54.40 0M25.60 32L57.60 0M28.80 32L60.80 0M32.00 32L64.00 0M35.20 32L67.20 0M38.40 32L70.40 0M41.60 32L73.60 0M44.80 32L76.80 0M48.00 32L80.00 0M51.20 32L83.20 0M54.40 32L86.40 0M57.60 32L89.60 0M60.80 32L92.80 0"
      stroke="var(--primary)"
      stroke-width="1.1"
      fill="none"
    />
  </g>
  <path
    d="M5.1 24.6V11.6a10 10 0 0 1 20 0v13q-3.333 5.6-6.667 0-3.333 5.6-6.666 0-3.333 5.6-6.667 0Z"
    fill="var(--marque-silhouette)"
  />
  <path
    d="M9.9 14.2 11.9 12 13.9 14.2M16.3 14.2 18.3 12 20.3 14.2"
    stroke="var(--marque-yeux)"
    stroke-width="1.9"
    stroke-linecap="round"
    stroke-linejoin="round"
    fill="none"
  />
</svg>
