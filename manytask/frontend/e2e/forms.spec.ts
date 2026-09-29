import {test, expect, asRole, openNavigation, payload} from './fixtures';

test('signup variants and native signup finish/enrollment with real CSRF', async ({page}) => {
  await page.goto('/signup'); expect((await payload(page)).page).toBe('signup');
  await page.getByLabel('Username',{exact:true}).fill('browsernew');
  await page.getByLabel('First name',{exact:true}).fill('Browser');
  await page.getByLabel('Last name',{exact:true}).fill('User');
  await page.getByLabel('Email address').fill('browser@example.test');
  await page.getByLabel('Password',{exact:true}).fill('abcdef');
  await page.getByLabel('Re-type password').fill('different');
  await page.getByRole('button',{name:'Sign up',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText("Passwords don't match");
  const signupName = `browserregister${Date.now()}`;
  await page.getByLabel('Username',{exact:true}).fill(signupName);
  await page.getByLabel('Re-type password').fill('abcdef');
  // OAuth itself is external; observe the real signup POST before its login handoff.
  await page.route('**/login',route=>route.fulfill({contentType:'text/plain',body:'Mock OAuth handoff'}));
  const signedUp=page.waitForResponse(response=>response.url().endsWith('/signup') && response.request().method()==='POST');
  await page.getByRole('button',{name:'Sign up',exact:true}).click();
  expect((await signedUp).status()).toBe(302);
  const rejected = await page.request.post('/signup',{form:{username:'badcsrf'}});
  expect(rejected.status()).toBe(400);
  await page.goto('/__preview__/sourcecraft'); expect((await payload(page)).page).toBe('signup-yandex-id');
  await expect(page.getByRole('link',{name:'Login with Yandex ID'})).toBeVisible();
  await page.screenshot({path:'../.tmp/sourcecraft-signin.png',fullPage:true});
  await page.goto(`/__preview__/signup-finish/browser${Date.now()}`);
  expect((await payload(page)).page).toBe('signup-finish');
  await page.getByLabel('First name',{exact:true}).fill('Browser');
  await page.getByLabel('Last name',{exact:true}).fill('User');
  await page.getByRole('button',{name:'Finish registration'}).click();
  await expect(page).toHaveURL('/');
  await page.goto('/sandbox/create_project'); expect((await payload(page)).page).toBe('create-project');
  await page.getByLabel('Secret Code').fill('invalid');
  await page.getByRole('button',{name:'Join course'}).click();
  await expect(page.getByRole('alert')).toContainText('Invalid secret');
  // Join empty so sandbox remains exactly230 rows for table/CSV assertions.
  await page.goto('/empty/create_project'); await page.getByLabel('Secret Code').fill('preview');
  await page.getByRole('button',{name:'Join course'}).click();
  await expect(page).toHaveURL('/empty/');
  await expect(page.locator('.app-content')).not.toBeEmpty();
});

test('native profile, course save and instance user management persist', async ({page}) => {
  await asRole(page,'instance_admin');
  await openNavigation(page);
  await page.getByRole('button',{name:'Change user info',exact:true}).click();
  const profileDialog = page.getByRole('dialog').filter({has: page.getByLabel('First name',{exact:true})});
  const firstName = profileDialog.getByLabel('First name',{exact:true});
  const updatedName = await firstName.inputValue() === 'Updated' ? 'Updated-Again' : 'Updated';
  await expect(firstName).not.toHaveValue(updatedName);
  await firstName.fill(updatedName);
  await Promise.all([
    page.waitForNavigation(),
    profileDialog.getByRole('button',{name:'Save',exact:true}).click(),
  ]);
  await page.reload();
  await openNavigation(page);
  await page.getByRole('button',{name:'Change user info',exact:true}).click();
  await expect(firstName).toHaveValue(updatedName);
  await profileDialog.getByRole('button',{name:'Cancel'}).click();
  await page.goto('/instance_admin/courses/sandbox/edit');
  const registrationSecret = page.getByLabel('Registration Secret',{exact:true});
  const originalSecret = await registrationSecret.inputValue();
  const updatedSecret = originalSecret === 'browser-enrollment' ? 'browser-enrollment-again' : 'browser-enrollment';
  await expect(registrationSecret).not.toHaveValue(updatedSecret);
  try {
    await registrationSecret.fill(updatedSecret);
    await Promise.all([page.waitForNavigation(), page.getByRole('button',{name:'Save changes'}).click()]);
    await page.goto('/instance_admin/courses/sandbox/edit');
    await page.reload();
    await expect(registrationSecret).toHaveValue(updatedSecret);
  } finally {
    // Other scenarios share this course's enrollment value, even after a failed assertion.
    await page.goto('/instance_admin/courses/sandbox/edit');
    await registrationSecret.fill(originalSecret);
    await Promise.all([page.waitForNavigation(), page.getByRole('button',{name:'Save changes'}).click()]);
    await page.goto('/instance_admin/courses/sandbox/edit');
    await expect(registrationSecret).toHaveValue(originalSecret);
  }
  await page.goto('/instance_admin/panel');
  await page.getByRole('button',{name:'Grant admin rights',exact:true}).click();
  const instanceRoleDialog = page.getByRole('dialog').filter({has: page.getByLabel('Select user')});
  await instanceRoleDialog.getByLabel('Select user').selectOption('student229');
  await page.getByRole('button',{name:'Grant Rights',exact:true}).click();
  await page.getByRole('textbox',{name:'Search users...',exact:true}).fill('student229');
  await expect(page.getByRole('row').filter({hasText:'student229'})).toContainText('Yes');
  await page.getByRole('button',{name:'Revoke admin rights',exact:true}).click();
  await instanceRoleDialog.getByLabel('Select user').selectOption('student229');
  await page.getByRole('button',{name:'Revoke Rights',exact:true}).click();
  await page.getByRole('textbox',{name:'Search users...',exact:true}).fill('student229');
  await expect(page.getByRole('row').filter({hasText:'student229'})).toContainText('No');
});

test('namespace membership create/change/delete through real handlers', async ({page}) => {
  await asRole(page,'namespace_admin'); await page.goto('/instance_admin/namespaces/1');
  await page.getByRole('button',{name:'Add user',exact:true}).click();
  const roleDialog = page.getByRole('dialog').filter({has: page.getByLabel('Role',{exact:true})});
  await roleDialog.getByLabel('Select user').selectOption('student228');
  await roleDialog.getByLabel('Role',{exact:true}).selectOption('program_manager');
  await page.getByRole('button',{name:'Assign role',exact:true}).click();
  await expect(roleDialog).toHaveCount(0);
  await page.reload(); await expect(page.getByRole('button',{name:'Change role student228'})).toBeVisible();
  await page.getByRole('button',{name:'Change role student228'}).click();
  await roleDialog.getByLabel('Role',{exact:true}).selectOption('namespace_admin');
  await page.getByRole('button',{name:'Save role'}).click();
  await expect(roleDialog).toHaveCount(0);
  await page.reload(); await expect(page.getByRole('row').filter({hasText:'student228'})).toContainText('Namespace Admin');
  await page.getByRole('button',{name:'Remove student228',exact:true}).click();
  const removeDialog = page.getByRole('dialog').filter({has: page.getByRole('button',{name:'Remove user',exact:true})});
  await removeDialog.getByRole('button',{name:'Remove user',exact:true}).click();
  await expect(removeDialog).toHaveCount(0);
  await page.reload(); await expect(page.getByRole('button',{name:'Change role student228'})).toHaveCount(0);
});


test('SourceCraft course layouts and native course creation', async ({page}) => {
  await asRole(page,'namespace_admin');
  await page.goto('/instance_admin/courses/new');
  const name=`browser-course-${Date.now()}`;
  await page.getByLabel('Unique Course Name',{exact:true}).fill(name);
  await page.getByLabel('Registration Secret',{exact:true}).fill('preview');
  await page.getByLabel('Course Token',{exact:true}).fill(`token-${name}`);
  await page.getByLabel('GitLab Course Group',{exact:true}).fill(name);
  await page.getByRole('button',{name:'Create course',exact:true}).click();
  await expect(page).not.toHaveURL('/instance_admin/courses/new');
  await page.goto(`/instance_admin/courses/${name}/edit`);
  await expect(page.getByLabel('Unique Course Name',{exact:true})).toHaveValue(name);
  await page.goto('/__preview__/sourcecraft');
  await page.goto('/instance_admin/courses/new');
  await expect(page.getByRole('heading',{name:'SourceCraft Configuration'})).toBeVisible();
  await expect(page.getByLabel('SourceCraft Course Prefix',{exact:true})).toBeVisible();
  await page.goto('/instance_admin/courses/sandbox/edit');
  await expect(page.getByRole('heading',{name:'SourceCraft Configuration'})).toBeVisible();
  await expect(page.locator('input[name="gitlab_course_group"]')).toHaveAttribute('type','hidden');
});
