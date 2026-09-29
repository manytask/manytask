import {test, expect, asRole, payload} from './fixtures';

for (const role of ['student', 'course_admin', 'namespace_admin', 'instance_admin']) {
  test(`real ${role} navigation and permissions`, async ({page}) => {
    await asRole(page, role);
    expect((await payload(page)).page).toBe('courses');
    for (const [url, name] of [['/sandbox/', 'assignments'], ['/sandbox/database', 'grades']] as const) {
      await page.goto(url);
      expect((await payload(page)).page).toBe(name);
      await expect(page.locator('.app-content')).not.toBeEmpty();
      if (name === 'grades') {
        await expect(page.getByText(role === 'student' ? '227 students' : '230 students', {exact:true})).toBeVisible();
        const data = await payload(page);
        expect(data.data.canEdit).toBe(role !== 'student');
        if (role === 'student') {
          await expect(page.getByRole('button', {name:'Hide personal info'})).toHaveCount(0);
          const scores = await page.request.get(data.data.urls.database);
          const text = await scores.text();
          expect(text).not.toContain('second line');
          const denied = await page.request.post(data.data.urls.updateScore, {data: {row_data: {username:'student000'}, new_scores: {add:99}}});
          expect(denied.status()).toBe(403);
        }
      }
    }
    const panel = await page.request.get('/instance_admin/panel');
    expect(panel.status()).toBe(role === 'instance_admin' ? 200 : 403);
    const edit = await page.request.get('/instance_admin/courses/sandbox/edit');
    expect(edit.status()).toBe(role === 'student' ? 403 : 200);
    if (role === 'namespace_admin' || role === 'instance_admin') {
      for (const [url, name] of [['/instance_admin/namespaces','namespaces'], ['/instance_admin/namespaces/1','namespace'], ['/instance_admin/courses/new','create-course']] as const) {
        await page.goto(url); expect((await payload(page)).page).toBe(name);
        await expect(page.locator('.app-content')).not.toBeEmpty();
      }
    }
    if (role !== 'student') {
      await page.goto('/instance_admin/courses/sandbox/edit'); expect((await payload(page)).page).toBe('edit-course');
    }
    if (role === 'instance_admin') {
      await page.goto('/instance_admin/panel'); expect((await payload(page)).page).toBe('instance-admin');
    }
    await page.goto('/pending/not_ready'); expect((await payload(page)).page).toBe('not-ready');
    await expect(page).toHaveTitle('pending');
    const icon = await page.locator('link[rel="icon"]').getAttribute('href');
    expect((await page.request.get(icon!)).status()).toBe(200);
  });
}

test('mobile navigation, keyboard theme, blocked storage and dialog focus', async ({page}) => {
  await page.setViewportSize({width:375,height:812});
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', {get() {throw new DOMException('Blocked', 'SecurityError');}});
  });
  await asRole(page);
  await page.goto('/sandbox/');
  const header = (await page.locator('.app-header').boundingBox())!;
  const main = (await page.locator('.app-content').boundingBox())!;
  expect(main.y).toBeGreaterThanOrEqual(header.y + header.height);
  await page.getByRole('button', {name:'Dark Theme'}).focus(); await page.keyboard.press('Enter');
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.getByRole('button', {name:'Light Theme'}).focus(); await page.keyboard.press('Space');
  await expect(page.locator('html')).toHaveAttribute('data-theme','light');
  await page.getByRole('button', {name:'Auto Theme'}).click();
  await page.emulateMedia({colorScheme:'dark'});
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.emulateMedia({colorScheme:'light'});
  await expect(page.locator('html')).toHaveAttribute('data-theme','light');
  const opener = page.getByRole('button', {name:'Change user info'});
  await opener.focus(); await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog'); await expect(dialog).toBeVisible();
  const box = (await dialog.boundingBox())!;
  expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(375);
  await dialog.getByRole('button', {name:'Cancel'}).click(); await expect(opener).toBeFocused();
  await page.screenshot({path:'../.tmp/mobile-assignments-light.png',fullPage:true});
  await page.goto('/sandbox/database');
  await expect(page.getByText('230 students',{exact:true})).toBeVisible();
  const widths = await page.locator('.grades-table-scroll').evaluate((el) => ({width:el.clientWidth, scroll:el.scrollWidth, body:document.documentElement.scrollWidth}));
  expect(widths.scroll).toBeGreaterThan(widths.width); expect(widths.body).toBeLessThanOrEqual(375);
  await page.screenshot({path:'../.tmp/mobile-grades-light.png',fullPage:true});
});
