import {test, expect, asRole, chooseTheme} from './fixtures';
import type {AssignmentsData} from '../src/pages/AssignmentsPage';

test('single-task groups stay compact and retain task links on desktop and mobile', async ({page}) => {
  await asRole(page);
  await page.goto('/sandbox/');
  const groups=page.locator('.assignment-group');
  const group=groups.filter({has:page.getByRole('heading',{name:'__proto__',exact:true})});
  await expect(group).toBeVisible();
  // With a normal desktop viewport, at least four single-task groups should fit
  // without scrolling. The previous nested-card layout only fit two.
  const visible=await groups.evaluateAll(items=>items.filter(item=>{
    const rect=item.getBoundingClientRect();
    return rect.top>=0 && rect.bottom<=window.innerHeight;
  }).length);
  expect(visible).toBeGreaterThanOrEqual(4);
  expect(await group.evaluate(el=>(el.textContent?.match(/-5\s*\/\s*100/g) ?? []).length)).toBe(1);
  await expect(group.getByRole('progressbar',{name:'Task completion',exact:true})).toHaveAttribute('aria-valuenow','0');
  const elapsed=Number(await group.getByRole('progressbar',{name:/^Time elapsed/}).getAttribute('aria-valuenow'));
  // This fixture has a future cutoff at full points. Time elapsed is separate
  // from that 100% scoring multiplier and from the student's negative score.
  expect(elapsed).toBeGreaterThan(0);
  expect(elapsed).toBeLessThan(100);
  const task=group.getByRole('link',{name:/dotted\.task/});
  const href=await task.getAttribute('href');
  expect(href).toContain('/__preview__/task/__proto__/dotted.task');
  const desktopGroup=(await group.boundingBox())!;
  expect((await task.boundingBox())!.width).toBeGreaterThan(desktopGroup.width*.75);

  await chooseTheme(page,'dark');
  await page.setViewportSize({width:375,height:812});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  const mobileGroup=(await group.boundingBox())!;
  expect((await task.boundingBox())!.width).toBeGreaterThan(mobileGroup.width*.75);
  await task.click();
  await expect(page).toHaveURL(href!);
});

test('multiple tasks and deadline stages remain readable on a narrow phone', async ({page}) => {
  await asRole(page);
  const longName='A_task_name_that_must_wrap_without_hiding_the_score_or_overflowing_the_phone';
  await page.route('**/sandbox/', async route => {
    const response=await route.fetch();
    const html=await response.text();
    const script=/<script id="manytask-page" type="application\/json">([\s\S]*?)<\/script>/;
    const envelope=JSON.parse(html.match(script)![1]) as {data:AssignmentsData};
    const group=envelope.data.groups[0];
    const task=group.tasks[0];
    // Exercise the real stylesheet with data shapes absent from the local
    // course template; the backend and stored course remain untouched.
    envelope.data.groups=[{...group,name:'Several tasks',earned:260,maximum:300,expired:false,graph:null,
      tasks:[{...task,name:longName,state:'partial',earned:40},
        {...task,name:'Solved',state:'solved',earned:100},
        {...task,name:'Bonus',state:'over_solved',earned:120,bonus:true},
        {...task,name:'Unsolved',state:'unsolved',earned:0}],
      deadlines:[1,.7,.5].map((percent,index)=>({
        at:`2026-10-${String(1+index*7).padStart(2,'0')}T12:00:00Z`,percent,
        passed:false,urgent:false,remaining:`Deadline expires in: ${2+index*7} d.`,
        progress:index===0?75:0,date:`${String(1+index*7).padStart(2,'0')}.10.2026`,time:'15:00',tz:'MSK',
      })),
    }];
    const json=JSON.stringify(envelope).replaceAll('<','\\u003c');
    await route.fulfill({response,body:html.replace(script,()=>`<script id="manytask-page" type="application/json">${json}</script>`)});
  });
  await page.goto('/sandbox/');
  const group=page.locator('.assignment-group');
  const tasks=group.locator('.assignment-task');
  await expect(tasks).toHaveCount(4);
  await expect(group.getByRole('progressbar',{name:'Task completion',exact:true})).toHaveAttribute('aria-valuenow','50');
  const desktop=await tasks.evaluateAll(items=>items.map(item=>{
    const rect=item.getBoundingClientRect();return {x:rect.x,y:rect.y};
  }));
  expect(desktop[0].y).toBe(desktop[1].y);
  expect(desktop[1].x).toBeGreaterThan(desktop[0].x);

  await page.setViewportSize({width:375,height:812});
  const mobile=await tasks.evaluateAll(items=>items.map(item=>{
    const rect=item.getBoundingClientRect();return {x:rect.x,y:rect.y,bottom:rect.bottom,width:rect.width};
  }));
  for(let i=1;i<mobile.length;i++) {
    expect(mobile[i].x).toBe(mobile[0].x);
    expect(mobile[i].y).toBeGreaterThanOrEqual(mobile[i-1].bottom);
  }
  const name=group.getByText(longName,{exact:true});
  expect((await name.boundingBox())!.height).toBeGreaterThan(30);
  const row=tasks.first();
  const score=await row.getByText('40/100',{exact:true}).boundingBox();
  const rowBox=(await row.boundingBox())!;
  expect(score!.x+score!.width).toBeLessThanOrEqual(rowBox.x+rowBox.width);
  for(const percent of [100,70,50]) await expect(group.getByText(new RegExp(`${percent}% of points until`))).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});
