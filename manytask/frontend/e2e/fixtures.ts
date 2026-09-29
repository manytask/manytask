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
  const breadcrumb = page.getByRole('navigation', {name: 'Breadcrumb'});
  await expect(breadcrumb.getByRole('link', {name: 'Manytask', exact: true})).toBeVisible();
}
export async function payload(page: Page) {
  return page.locator('#manytask-page').evaluate((node) => JSON.parse(node.textContent!));
}

export async function openNavigation(page: Page): Promise<void> {
  const drawer = page.getByRole('dialog', {name: 'Navigation'});
  if (await drawer.isVisible().catch(() => false)) return;
  const opener = page.getByRole('button', {name: 'Open navigation'});
  if (await opener.isVisible().catch(() => false)) {
    await opener.click();
    await expect(drawer).toBeVisible();
  }
}

export async function closeNavigation(page: Page): Promise<void> {
  const closer = page.getByRole('button', {name: 'Close navigation'});
  if (await closer.isVisible().catch(() => false)) {
    await closer.click();
    await expect(page.getByRole('dialog', {name: 'Navigation'})).toHaveCount(0);
  }
}

export async function chooseTheme(page: Page, theme: 'light' | 'dark' | 'auto'): Promise<void> {
  await openNavigation(page);
  const menu = page.locator('details.appearance-menu');
  const appearance = page.locator('summary[aria-label="Appearance"]');
  if (await menu.getAttribute('open') === null) await appearance.click();
  const label = `${theme === 'auto' ? 'Auto' : theme === 'dark' ? 'Dark' : 'Light'} Theme`;
  await page.getByRole('button', {name: label, exact: true}).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', theme === 'auto' ? /^(light|dark)$/ : theme);
  if (await menu.getAttribute('open') !== null) await appearance.click();
  await closeNavigation(page);
}
