import {test, expect, asRole} from './fixtures';

test('course card edges behave as a native link', async ({page, context}) => {
  await asRole(page, 'instance_admin');
  const listUrl = page.url();
  const card = page.locator('.courses-list li').filter({has: page.getByRole('link', {name: 'sandbox', exact: true})});
  const link = card.getByRole('link', {name: 'sandbox', exact: true});
  const href = await link.getAttribute('href');
  await card.hover();
  await card.evaluate((element) => Promise.all(element.getAnimations().map((animation) => animation.finished)));

  const edgeTargets = await card.evaluate((element) => {
    const {left, top, width, height} = element.getBoundingClientRect();
    return [[0.5, height / 2], [width - 0.5, height / 2], [width / 2, 0.5], [width / 2, height - 0.5]].map(([x, y]) => {
      const target = document.elementFromPoint(left + x, top + y);
      return target?.closest('a')?.getAttribute('href') ?? null;
    });
  });
  expect(edgeTargets).toEqual([href, href, href, href]);

  const {width, height} = (await card.boundingBox())!;
  const position = {x: width - 4, y: height / 2};
  const [tab] = await Promise.all([
    context.waitForEvent('page'),
    card.click({position, button: 'middle'}),
  ]);
  await expect(tab).toHaveURL(/\/sandbox\/$/);
  await tab.close();
  await expect(page).toHaveURL(listUrl);

  await card.click({position});
  await expect(page).toHaveURL(/\/sandbox\/$/);
  await page.goBack();
  await link.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/sandbox\/$/);
});
