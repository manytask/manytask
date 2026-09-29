import {test, expect, asRole, chooseTheme} from './fixtures';

// Playwright normally hides the native scrollbars, masking their layout and theme.
test.use({launchOptions: {ignoreDefaultArgs: ['--hide-scrollbars']}});

for (const theme of ['light', 'dark'] as const) {
  test(`keeps grades scrollbars visible and usable in ${theme} theme`, async ({page}) => {
    await asRole(page, 'student');
    await page.goto('/sandbox/database');
    await expect(page.getByText('227 students', {exact: true})).toBeVisible();
    await chooseTheme(page, theme);

    const scroll = page.locator('.grades-table-scroll');
    const layout = await scroll.evaluate((element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return {
        x: rect.x + element.clientLeft,
        y: rect.y + element.clientTop,
        width: element.clientWidth,
        height: element.clientHeight,
        verticalBar: element.offsetWidth - element.clientWidth - parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth),
        horizontalBar: element.offsetHeight - element.clientHeight - parseFloat(style.borderTopWidth) - parseFloat(style.borderBottomWidth),
        background: style.backgroundColor,
        scrollbar: style.scrollbarColor,
      };
    });
    // A themed track must blend into the table instead of drawing an OS-colored strip.
    expect(layout.scrollbar).toContain(layout.background);
    expect(layout.verticalBar).toBeGreaterThan(0);
    expect(layout.horizontalBar).toBeGreaterThan(0);

    // Drag the actual native thumbs; setting scrollTop/Left would not test their usability.
    await page.mouse.move(layout.x + layout.width + layout.verticalBar / 2, layout.y + 20);
    await page.mouse.down();
    await page.mouse.move(layout.x + layout.width + layout.verticalBar / 2, layout.y + layout.height - 20, {steps: 10});
    await page.mouse.up();
    await expect.poll(() => scroll.evaluate((element) => element.scrollTop + element.clientHeight)).toBeGreaterThanOrEqual(
      await scroll.evaluate((element) => element.scrollHeight - 1),
    );

    await page.mouse.move(layout.x + 20, layout.y + layout.height + layout.horizontalBar / 2);
    await page.mouse.down();
    await page.mouse.move(layout.x + layout.width - 20, layout.y + layout.height + layout.horizontalBar / 2, {steps: 10});
    await page.mouse.up();
    await expect.poll(() => scroll.evaluate((element) => element.scrollLeft + element.clientWidth)).toBeGreaterThanOrEqual(
      await scroll.evaluate((element) => element.scrollWidth - 1),
    );

    const lastCell = await scroll.locator('tbody tr:last-child td:last-child').boundingBox();
    expect(lastCell).not.toBeNull();
    expect(lastCell!.x + lastCell!.width).toBeLessThanOrEqual(layout.x + layout.width + 1);
    expect(lastCell!.y + lastCell!.height).toBeLessThanOrEqual(layout.y + layout.height + 1);
    await page.screenshot({path: `../.tmp/grades-scrollbars-${theme}.png`, animations: 'disabled'});
  });
}
