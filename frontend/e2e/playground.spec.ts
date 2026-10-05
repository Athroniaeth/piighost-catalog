import { expect, test } from "@playwright/test";

test.describe("the playground", () => {
  test("opens on a sample and runs it", async ({ page }) => {
    await page.goto("/playground");
    const text = page.getByLabel("Text", { exact: true });
    await expect(text).not.toHaveValue("");

    await page.getByRole("button", { name: "Run", exact: true }).click();
    // Detections land in the results column, with their label.
    await expect(page.getByText(/kept/)).toBeVisible();
    await expect(page.locator("main").getByText("IPV4").first()).toBeVisible();
  });

  test("opens its panel outside every clipping ancestor", async ({ page }) => {
    // The group's source rows sit in a scroller inside a card that clips to
    // draw its corners. An absolutely positioned panel was cut by whichever
    // came first, and arrived as a sliver showing its filter and nothing else.
    await page.goto("/contribute");
    await page.getByRole("button", { name: /group/i }).click();
    await page.getByRole("button", { name: "Add a source" }).click();
    await page.getByRole("button", { name: "Add a source" }).click();

    await page.locator("[id^=source-]").last().click();
    const panel = page.getByRole("listbox");
    await expect(panel).toBeVisible();
    await expect(panel.getByRole("option").first()).toBeVisible();

    const box = await panel.boundingBox();
    const viewport = page.viewportSize()!;
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1);
    // Enough of the list to choose from, not a sliver.
    expect(await panel.getByRole("option").count()).toBeGreaterThan(20);
  });

  test("keeps its options out of the DOM until it is opened", async ({
    page,
  }) => {
    // Two hundred options per picker, times one per detector row, is a lot of
    // DOM for a list nobody has opened.
    // Scoped to the picker: a native select's own options carry the same role.
    await page.goto("/playground");
    await expect(page.getByRole("listbox")).toHaveCount(0);
    await page.locator("#play-ref").click();
    const panel = page.getByRole("listbox");
    // `count()` does not retry, and the contents render a tick after the panel.
    await expect(panel.getByRole("option").first()).toBeVisible();
    expect(await panel.getByRole("option").count()).toBeGreaterThan(20);
  });

  test("shows the coverage count on every row of the object picker", async ({
    page,
  }) => {
    // This shipped broken once: the number was in the DOM, at coordinates
    // inside the popover, and an ancestor's overflow painted it away. Only a
    // browser sees that, so only a browser can guard it.
    await page.goto("/playground");
    await page.locator("#play-ref").click();

    const listbox = page.getByRole("listbox");
    const options = listbox.getByRole("option");
    await expect(options.first()).toBeVisible();

    const box = await listbox.boundingBox();
    const rows = await options.all();
    for (const row of rows.slice(0, 5)) {
      await expect(row).toContainText(/\d+$/);
      const count = row.locator("span").last();
      const rect = await count.boundingBox();
      expect(rect).not.toBeNull();
      expect(rect!.width).toBeGreaterThan(0);
      expect(rect!.x + rect!.width).toBeLessThanOrEqual(
        box!.x + box!.width + 1,
      );
    }
  });

  test("scrolls the object picker under the wheel", async ({ page }) => {
    // The panel repositions itself on scroll, and the listener captures, so it
    // also heard the listbox's own scroll and fought every wheel tick. The
    // list looked frozen at two hundred entries. Only a real wheel shows it.
    await page.goto("/playground");
    await page.locator("#play-ref").click();

    const listbox = page.getByRole("listbox");
    await expect(listbox.getByRole("option").first()).toBeVisible();
    const box = await listbox.boundingBox();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
    for (let tick = 0; tick < 4; tick += 1) {
      await page.mouse.wheel(0, 120);
      await page.waitForTimeout(80);
    }
    expect(await listbox.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
  });

  test("leads with the groups in the picker", async ({ page }) => {
    // The catalog is a registry of regexes: a group is the set someone came to
    // run, a piighost config is a different object further down.
    await page.goto("/playground");
    await page.locator("#play-ref").click();
    const options = page.getByRole("listbox").getByRole("option");
    await expect(options.first()).toHaveAttribute("title", /• group •/);
  });

  // The chat demo is off: see CHAT_ENABLED in src/lib/router.svelte.ts. The
  // page is kept, so this stays skipped rather than deleted.
  test.skip("shows what the model sees, checked from the start", async ({
    page,
  }) => {
    await page.goto("/playground/chat");
    await expect(page.getByRole("checkbox")).toBeChecked();
    await page.getByRole("button", { name: "Send" }).click();
    // The placeholder is what leaves, and it is coloured like a detection.
    await expect(
      page
        .locator("main")
        .getByText(/<<EMAIL:1>>/)
        .first(),
    ).toBeVisible();
  });
});
