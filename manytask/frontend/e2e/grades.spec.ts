import {readFile} from 'node:fs/promises';
import type {Locator, Page} from '@playwright/test';
import {test, expect, asRole, chooseTheme, payload} from './fixtures';

async function width(cell: Locator, expected: number) {
  await expect.poll(async () => Math.abs((await cell.boundingBox())!.width - expected), {message: `${await cell.textContent()} should be ${expected}px`}).toBeLessThanOrEqual(2);
}
async function resize(page: Page, cell: Locator, target: number) {
  await cell.scrollIntoViewIfNeeded();
  const before = (await cell.boundingBox())!;
  const handle = cell.locator('[class*="resize-handle"]').first();
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down(); await page.mouse.move(box.x + box.width / 2 + target - before.width, box.y + box.height / 2, {steps:10});
  await page.mouse.up(); await width(cell,target);
}
async function expectHeaderOwnsCenterPoint(header: Locator) {
  await expect.poll(() => header.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return hit != null && element.contains(hit);
  }), {message: `${await header.textContent()} header should paint above body cells`}).toBe(true);
}
// RFC4180 parser: unlike split-lines it detects quoted embedded newlines and quotes.
function parseCsv(csv: string): string[][] {
  const rows: string[][] = []; let row: string[] = []; let field = ''; let quoted = false;
  for (let i=0;i<csv.length;i++) {
    const c=csv[i];
    if (c==='"') {if (quoted && csv[i+1]==='"') {field+='"';i++;} else quoted=!quoted;}
    else if (c===',' && !quoted) {row.push(field);field='';}
    else if (c==='\n' && !quoted) {row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}
    else field+=c;
  }
  if (field || row.length) {row.push(field);rows.push(row);}
  return rows;
}

test('sticky grade headers own hit testing after combined table scrolling', async ({page}) => {
  await asRole(page); await page.goto('/sandbox/database');
  await expect(page.getByText('230 students',{exact:true})).toBeVisible();
  const scroll=page.locator('.grades-table-scroll');
  const username=page.getByRole('columnheader',{name:'Username',exact:true});
  const task=page.getByRole('columnheader',{name:'add_cpp',exact:true});

  await scroll.evaluate(el=>{el.scrollLeft=el.scrollWidth;el.scrollTop=300;});
  await expectHeaderOwnsCenterPoint(username);
  await expectHeaderOwnsCenterPoint(task);

  await page.setViewportSize({width:375,height:812});
  await chooseTheme(page,'dark');
  await scroll.evaluate(el=>{el.scrollLeft=el.scrollWidth;el.scrollTop=300;});
  await expectHeaderOwnsCenterPoint(username);
  await expectHeaderOwnsCenterPoint(task);
});

test('physical widths, pinning, sticky headers and edit reload preserve table state', async ({page}) => {
  await asRole(page); await page.goto('/sandbox/database');
  await expect(page.getByText('230 students',{exact:true})).toBeVisible();
  const username = page.getByRole('columnheader',{name:'Username',exact:true});
  await resize(page,username,190);
  await username.getByRole('button').click();
  await page.getByRole('button',{name:'Hide personal info'}).click();
  const task = page.getByRole('columnheader',{name:'add_cpp',exact:true});
  await resize(page,task,175);
  await page.getByRole('button',{name:'Collapse python',exact:true}).click();
  const summary = () => page.getByRole('columnheader',{name:'Total',exact:true});
  await resize(page,summary(),195);
  await page.getByRole('button',{name:'Collapse rust',exact:true}).click();
  await page.getByRole('textbox',{name:'Search students'}).fill('student');
  await page.getByRole('button',{name:'Next page',exact:true}).click();
  for (const name of ['Show oldest first','Show newest first']) {
    await page.getByRole('button',{name,exact:true}).click();
    await expect(page.getByText('Page 2 of 3',{exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Expand python'})).toBeVisible();
    await width(username,190); await width(task,175);
    // Python starts at the same date as cpp; stable ordering still follows group identity.
    const python = page.getByRole('columnheader').filter({has:page.getByRole('button',{name:'Expand python'})});
    await width(python,195);
  }
  const scroll = page.locator('.grades-table-scroll');
  await scroll.evaluate((el) => {el.scrollLeft=0;el.scrollTop=0;});
  const original = (await username.boundingBox())!;
  await scroll.evaluate((el) => {el.scrollLeft=500;el.scrollTop=300;});
  const pinned = (await username.boundingBox())!;
  expect(Math.abs(pinned.x-original.x)).toBeLessThanOrEqual(2);
  expect(Math.abs(pinned.y-original.y)).toBeLessThanOrEqual(2);
  await scroll.evaluate((el) => {el.scrollTop=0;});
  await page.getByRole('button',{name:'Expand python'}).click();
  await width(task,175); await width(username,190);
  const scoreButton = page.getByRole('button',{name:/^Edit score add_cpp for /}).first();
  const editName = (await scoreButton.getAttribute('aria-label'))!.replace('Edit score add_cpp for ','');
  await scoreButton.click();
  const scoreInput = page.getByLabel('Score',{exact:true});
  const updatedScore = Number(await scoreInput.inputValue()) === 37 ? '38' : '37';
  await expect(scoreInput).not.toHaveValue(updatedScore);
  await scoreInput.fill(updatedScore);
  await page.getByRole('dialog').getByRole('button',{name:'Save',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button',{name:`Edit score add_cpp for ${editName}`,exact:true})).toBeFocused();
  await expect(page.getByText('Page 2 of 3',{exact:true})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'Search students'})).toHaveValue('student');
  await expect(page.getByRole('button',{name:'Expand rust'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Show oldest first'})).toBeVisible();
  await width(username,190); await width(task,175);
  // A score may move the edited row due to total-score sorting; find it via real search.
  await expect(page.getByRole('button',{name:`Edit score add_cpp for ${editName}`,exact:true})).toHaveText(updatedScore);
  await page.getByRole('button',{name:`Edit grade for ${editName}`,exact:true}).click();
  const gradeInput = page.getByLabel('Grade',{exact:true});
  const updatedGrade = Number(await gradeInput.inputValue()) === 4 ? '5' : '4';
  await expect(gradeInput).not.toHaveValue(updatedGrade);
  await gradeInput.fill(updatedGrade);
  await page.getByRole('dialog').getByRole('button',{name:'Save',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button',{name:`Edit grade for ${editName}`,exact:true})).toBeFocused();
  await expect(page.getByText('Page 2 of 3',{exact:true})).toBeVisible();
  await width(username,190); await width(task,175);
  await page.getByRole('button',{name:'Show personal info'}).click();
  await page.getByRole('button',{name:`Edit comment for ${editName}`,exact:true}).click();
  const commentInput = page.getByLabel('Comment',{exact:true});
  const safetyComment = 'Browser "saved"\n<img onerror=alert(1)> &quot; &amp;';
  const updatedComment = await commentInput.inputValue() === safetyComment ? `${safetyComment}\nUpdated again` : safetyComment;
  await expect(commentInput).not.toHaveValue(updatedComment);
  await commentInput.fill(updatedComment);
  await page.getByRole('dialog').getByRole('button',{name:'Save',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button',{name:`Edit comment for ${editName}`,exact:true})).toBeFocused();
  await expect(page.getByText('Page 2 of 3',{exact:true})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'Search students'})).toHaveValue('student');
  await expect(page.getByRole('button',{name:'Expand rust'})).toBeVisible();
  await width(username,190); await width(task,175);
  await page.reload(); await page.getByRole('textbox',{name:'Search students'}).fill(editName);
  await expect(page.getByRole('button',{name:`Edit score add_cpp for ${editName}`,exact:true})).toHaveText(updatedScore);
  await expect(page.getByRole('button',{name:`Edit grade for ${editName}`,exact:true})).toHaveText(`${updatedGrade} *`);
  await expect(page.getByRole('button',{name:`Edit comment for ${editName}`,exact:true})).toHaveText(updatedComment);
  await page.getByRole('button',{name:`Edit comment for ${editName}`,exact:true}).click();
  await expect(commentInput).toHaveValue(updatedComment);
  await page.getByRole('dialog').getByRole('button',{name:'Cancel'}).click();
  await expect(page.locator('.grades-table-scroll img')).toHaveCount(0);
  await chooseTheme(page,'dark');
  // UIKit transitions button colors for150ms; assert the settled palette before capture.
  await expect(page.getByRole('button',{name:`Edit comment for ${editName}`,exact:true})).toHaveCSS('color','rgba(255, 255, 255, 0.85)');
  await page.getByRole('textbox',{name:'Search students'}).fill('');
  await page.screenshot({path:'../.tmp/desktop-grades-dark.png',fullPage:true,animations:'disabled'});
});

test('real CSV download is complete after immediate object URL revocation', async ({page}) => {
  await asRole(page); await page.goto('/sandbox/database');
  await expect(page.getByText('230 students',{exact:true})).toBeVisible();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button',{name:'Download CSV'}).click();
  const download = await downloaded; expect(await download.failure()).toBeNull();
  await download.saveAs('../.tmp/grades-export.csv');
  const rows=parseCsv((await readFile((await download.path())!,'utf8')).replace(/^\uFEFF/,''));
  expect(rows).toHaveLength(231);
  const columns=rows[0];const student=rows.find((row)=>row[columns.indexOf('username')]==='student000')!;
  expect(student[columns.indexOf('scores.add')]).toBe('0');
  expect(student[columns.indexOf('comment')]).toBe('Unicode Иван, "quoted"\nsecond line');
  expect(rows.every(row=>row.length===columns.length)).toBe(true);
});

test('pending fetch, network retry and empty responses stay usable', async ({page}) => {
  await asRole(page); await page.goto('/sandbox/database');
  await expect(page.getByText('230 students',{exact:true})).toBeVisible();
  const url=(await payload(page)).data.urls.database;
  let release!: () => void; const pending=new Promise<void>(resolve=>{release=resolve;});
  await page.route(url,async route=>{await pending;await route.continue();},{times:1});
  await page.getByRole('button',{name:'Reload grades'}).click();
  await expect(page.getByRole('button',{name:'Reload grades'})).toBeDisabled();
  await page.getByRole('button',{name:'Show oldest first'}).click();
  await page.getByRole('textbox',{name:'Search students'}).fill('student');
  release(); await expect(page.getByRole('button',{name:'Reload grades'})).toBeEnabled();
  await page.route(url,route=>route.abort(),{times:1});
  await page.getByRole('button',{name:'Reload grades'}).click();
  await expect(page.getByRole('alert')).toContainText('Unable to load grades');
  await page.getByRole('button',{name:'Retry',exact:true}).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  // Fault injection only for exceptional response contracts; normal scenarios use real APIs/Table.
  await page.route(url,async route=>{
    const response=await route.fetch(); const data=await response.json();
    await route.fulfill({json:{...data,students:[],tasks:[]}});
  },{times:1});
  await page.getByRole('button',{name:'Reload grades'}).click();
  await expect(page.getByText('No students found')).toBeVisible();
});

test('narrow table keeps resized identity while tasks remain reachable after ordering and reload', async ({page}) => {
  await asRole(page);await page.goto('/sandbox/database');
  await expect(page.getByText('230 students',{exact:true})).toBeVisible();
  const username=page.getByRole('columnheader',{name:'Username',exact:true});
  await resize(page,username,190);
  await page.setViewportSize({width:375,height:812});
  await page.getByRole('button',{name:'Show oldest first'}).click();
  await page.getByRole('button',{name:'Reload grades'}).click();
  await expect(page.getByRole('button',{name:'Reload grades'})).toBeEnabled();
  await width(username,190);
  const scroll=page.locator('.grades-table-scroll');
  await scroll.evaluate(el=>{el.scrollLeft=el.scrollWidth;});
  const task=page.getByRole('button',{name:/^Edit score dotted.task for /}).first();
  await task.click({timeout:5000});
  const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
  const box=(await dialog.boundingBox())!;expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(375);
  await dialog.getByRole('button',{name:'Cancel'}).click();
  await expect(task).toBeFocused();
  for (const name of [/^Edit grade for /, /^Edit comment for /]) {
    const button=page.getByRole('button',{name}).first();
    await button.scrollIntoViewIfNeeded();
    const position=(await button.boundingBox())!;
    await scroll.evaluate((el, x)=>{el.scrollLeft+=x-250;},position.x);
    await button.click();await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('dialog').getByRole('button',{name:'Cancel'}).click();
    await expect(button).toBeFocused();
  }
  const nameBox=(await username.boundingBox())!;const scrollBox=(await scroll.boundingBox())!;
  const rowNumberBox=(await page.getByRole('columnheader',{name:'#',exact:true}).boundingBox())!;
  expect(Math.abs(nameBox.x-scrollBox.x-rowNumberBox.width)).toBeLessThanOrEqual(2);
  const lightTableBackground=await scroll.evaluate(el=>getComputedStyle(el).backgroundColor);
  expect(lightTableBackground).not.toBe('rgba(0, 0, 0, 0)');
  await expect(username).toHaveCSS('background-color',lightTableBackground);
  await expect(page.locator('.gt-table__cell_id_username').first()).toHaveCSS('background-color',lightTableBackground);
  await page.screenshot({path:'../.tmp/mobile-grades-scrolled.png',fullPage:true});
  await chooseTheme(page,'dark');
  const darkTableBackground=await scroll.evaluate(el=>getComputedStyle(el).backgroundColor);
  expect(darkTableBackground).not.toBe('rgba(0, 0, 0, 0)');
  await expect(username).toHaveCSS('background-color',darkTableBackground);
  await expect(page.locator('.gt-table__cell_id_username').first()).toHaveCSS('background-color',darkTableBackground);
  await page.screenshot({path:'../.tmp/mobile-grades-scrolled-dark.png',fullPage:true,animations:'disabled'});
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Collapse navigation',exact:true}).click();
  await width(username,190);
  const grade=page.getByRole('columnheader',{name:'Grade',exact:true});
  await expect(grade).toHaveClass(/gt-table__header-cell_pinned/);
  await scroll.evaluate(el=>{el.scrollLeft=0;});const before=(await grade.boundingBox())!;
  await scroll.evaluate(el=>{el.scrollLeft=500;});const after=(await grade.boundingBox())!;
  expect(Math.abs(before.x-after.x)).toBeLessThanOrEqual(2);
});

test('sidebar width changes keep task columns reachable and pin full metadata only when it fits', async ({page}) => {
  await page.setViewportSize({width:1024,height:900});
  await asRole(page);await page.goto('/sandbox/database');
  await expect(page.getByText('230 students',{exact:true})).toBeVisible();
  const scroll=page.locator('.grades-table-scroll');
  const firstName=page.getByRole('columnheader',{name:'First Name',exact:true});
  await expect(firstName).not.toHaveClass(/gt-table__header-cell_pinned/);
  const expandedWidth=await scroll.evaluate(el=>el.clientWidth);

  await page.getByRole('button',{name:'Collapse navigation',exact:true}).click();
  await expect(page.getByRole('button',{name:'Expand navigation',exact:true})).toBeVisible();
  await expect.poll(()=>scroll.evaluate(el=>el.clientWidth)).toBeGreaterThan(expandedWidth);
  await expect(firstName).not.toHaveClass(/gt-table__header-cell_pinned/);
  await scroll.evaluate(el=>{el.scrollLeft=el.scrollWidth;});
  await expect(page.getByRole('columnheader',{name:'add_cpp',exact:true})).toBeVisible();

  await page.setViewportSize({width:1440,height:900});
  await expect(firstName).toHaveClass(/gt-table__header-cell_pinned/);
});
