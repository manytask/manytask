import {test as base, expect, type Page} from '@playwright/test';

export const test = base.extend<{browserErrors: string[]}>({
  browserErrors: [async ({page}, use) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (response.url().includes('/static/') && response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
    });
    page.on('requestfailed', (request) => {
      if (request.url().includes('/static/')) errors.push(`Failed asset ${request.url()}`);
    });
    await use(errors);
    expect(errors, 'uncaught errors / failed static assets').toEqual([]);
  }, {auto: true}],
});
export {expect};
export async function asRole(page: Page, role = 'course_admin') {
  await page.goto(`/__preview__/as/${role}`);
  await expect(page.getByText('Manytask', {exact: true})).toBeVisible();
}
export async function payload(page: Page) {
  return page.locator('#manytask-page').evaluate((node) => JSON.parse(node.textContent!));
}
