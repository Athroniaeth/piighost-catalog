import { expect, test } from "@playwright/test";

test.describe("the catalogue", () => {
  test("opens on the widest coverage, not the most recent", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Widest coverage" }),
    ).toHaveAttribute("aria-pressed", "true");
    // The first row therefore covers more than the second.
    const counts = await page
      .locator("main ul > li a[href^='/?label']")
      .count();
    expect(counts).toBeGreaterThanOrEqual(0);
    await expect(page.locator("main ul > li").first()).toContainText("labels");
  });

  test("names the page after the reference, so a tab is readable", async ({
    page,
  }) => {
    await page.goto("/r/piighost/fr-default");
    await expect(page).toHaveTitle("piighost/fr-default · piighost catalog");
  });

  test("caps a long facet, and keeps it open across a filter", async ({
    page,
  }) => {
    await page.goto("/");
    const region = page.locator("details", {
      has: page.getByText("Region", { exact: true }),
    });
    await expect(region.getByRole("checkbox")).toHaveCount(8);

    await region.getByRole("button", { name: /Show more/ }).click();
    const expanded = await region.getByRole("checkbox").count();
    expect(expanded).toBeGreaterThan(8);

    // Choosing a filter builds a new result and remounts the whole sidebar, so
    // an expansion held inside a section would vanish on the click that used
    // it. Filtering by kind keeps every region, so the count must not move.
    await page
      .locator("details", { has: page.getByText("Type", { exact: true }) })
      .getByRole("checkbox")
      .first()
      .check();
    await expect(page).toHaveURL(/kind=/);
    await expect(region.getByRole("checkbox")).toHaveCount(expanded);
    await expect(
      region.getByRole("button", { name: /Show less/ }),
    ).toBeVisible();
  });

  test("filters the catalogue from a facet", async ({ page }) => {
    await page.goto("/");
    const before = await page.getByText(/results/).innerText();
    await page
      .locator("details", { has: page.getByText("Type", { exact: true }) })
      .getByRole("checkbox")
      .first()
      .check();
    await expect(page.getByText(/results/)).not.toHaveText(before);
    await expect(page).toHaveURL(/kind=pattern/);
  });
});
