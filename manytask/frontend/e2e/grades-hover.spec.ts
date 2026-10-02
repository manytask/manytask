import {test, expect, asRole, chooseTheme} from './fixtures';

for (const theme of ['light', 'dark'] as const) {
  test(`highlights the entire grades row on hover in ${theme} theme`, async ({page}) => {
    await asRole(page, 'student');
    await page.goto('/sandbox/database');
    await expect(page.getByText('227 students', {exact: true})).toBeVisible();
    await chooseTheme(page, theme);

    const scroll = page.locator('.grades-table-scroll');
    const row = scroll.locator('tbody tr').nth(1);
    const username = row.locator('.gt-table__cell_id_username');
    const backgrounds = () => row.locator('td').evaluateAll((cells) => cells.map((cell) => {
      const style = getComputedStyle(cell);
      return {color: style.backgroundColor, image: style.backgroundImage};
    }));
    const idle = await username.evaluate((cell) => {
      const style = getComputedStyle(cell);
      return {color: style.backgroundColor, image: style.backgroundImage};
    });

    for (const edge of ['start', 'end'] as const) {
      await scroll.evaluate((element, edge) => {
        element.scrollLeft = edge === 'start' ? 0 : element.scrollWidth;
      }, edge);
      const score = row.locator('.gt-table__cell:not(.gt-table__cell_pinned)').last();
      for (const target of [username, score]) {
        await target.hover();
        await expect.poll(async () => {
          const cells = await backgrounds();
          return cells.every((cell) => JSON.stringify(cell) === JSON.stringify(cells[0]));
        }, {message: 'Pinned and scrolling cells should share the same hover background'}).toBe(true);
        const cells = await backgrounds();
        expect(cells[0]).not.toEqual(idle);
        // Hover must retain an opaque base so scrolled text cannot show through.
        expect(cells[0].color).toMatch(/^rgb\(/);
      }
    }

    await page.screenshot({path: `../.tmp/all-scores-hover-${theme}.png`, animations: 'disabled'});
    await page.getByRole('heading', {name: 'Course Database'}).hover();
    await expect.poll(() => username.evaluate((cell) => {
      const style = getComputedStyle(cell);
      return {color: style.backgroundColor, image: style.backgroundImage};
    })).toEqual(idle);
    await expect(page.getByRole('button', {name: /Show (oldest|newest) first/})).toHaveCount(0);
  });
}
