import {test, expect, asRole, chooseTheme, openNavigation} from './fixtures';

test.use({launchOptions: {ignoreDefaultArgs: ['--hide-scrollbars']}});

for (const theme of ['light', 'dark'] as const) {
  test(`course picker contains its scrollbar in ${theme} theme`, async ({page}) => {
    // Exercise overflow even on a fresh preview database with only a few courses.
    await page.route('**/', async (route) => {
      const response = await route.fetch();
      const html = await response.text();
      const script = /<script id="manytask-page" type="application\/json">([\s\S]*?)<\/script>/;
      const envelope = JSON.parse(html.match(script)![1]);
      envelope.shared.courses = Array.from({length: 20}, (_, index) => ({
        label: `Course ${index + 1} with a long name`, href: `/sandbox/?picker-test=${index}`,
      }));
      const json = JSON.stringify(envelope).replaceAll('<', '\\u003c');
      await route.fulfill({response, body: html.replace(script, () => `<script id="manytask-page" type="application/json">${json}</script>`)});
    });
    await asRole(page, 'instance_admin');
    await page.goto('/');
    await chooseTheme(page, theme);

    for (const layout of ['expanded', 'collapsed', 'mobile']) {
      if (layout === 'collapsed') await page.getByRole('button', {name: 'Collapse navigation'}).click();
      if (layout === 'mobile') {
        await page.setViewportSize({width: 375, height: 812});
        await openNavigation(page);
      }
      await page.locator('summary[aria-label="Switch course"]').click();
      const menu = page.getByRole('navigation', {name: 'Courses', exact: true});
      await expect(menu.getByRole('link')).toHaveCount(20);
      // The same menu retains its scroll position when the sidebar collapses.
      await menu.evaluate((element) => {element.scrollTop = 0;});
      const geometry = await menu.evaluate((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return {
          x: rect.x + element.clientLeft, y: rect.y + element.clientTop,
          width: element.clientWidth, height: element.clientHeight,
          bar: element.offsetWidth - element.clientWidth - parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth),
          scrollbar: style.scrollbarColor, background: style.backgroundColor,
        };
      });
      expect(geometry.scrollbar).toContain(geometry.background);
      expect(geometry.bar).toBeGreaterThan(0);
      const frame = (await page.locator('.course-switcher__panel').boundingBox())!;
      expect(geometry.x).toBeGreaterThan(frame.x);
      expect(geometry.x + geometry.width + geometry.bar).toBeLessThan(frame.x + frame.width);
      expect(geometry.y + geometry.height).toBeLessThan(frame.y + frame.height);

      const barX = geometry.x + geometry.width + geometry.bar / 2;
      await page.mouse.move(barX, geometry.y + 20);
      await page.mouse.down();
      await page.mouse.move(barX, geometry.y + geometry.height - 10, {steps: 10});
      await page.mouse.up();
      await expect.poll(() => menu.evaluate((element) => element.scrollTop + element.clientHeight)).toBeGreaterThanOrEqual(
        await menu.evaluate((element) => element.scrollHeight - 1),
      );
      await page.screenshot({path: `../.tmp/course-picker-${theme}-${layout}.png`});
      if (layout === 'mobile') {
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
        await menu.getByRole('link').last().click();
        await expect(page).toHaveURL(/\/sandbox\/\?picker-test=19$/);
      } else {
        await page.locator('summary[aria-label="Switch course"]').click();
      }
    }
  });
}
