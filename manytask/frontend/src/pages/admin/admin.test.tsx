import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {renderUi, makeSharedUi} from '../../test/render';
import {InstanceAdminPage} from './InstanceAdminPage';
import {NamespacesPage} from './NamespacesPage';
import {NamespacePage} from './NamespacePage';

const namespace = {id: 1, name: 'Учебный', slug: 'study', description: 'Description', gitlabGroupId: 12, usersCount: 1, coursesCount: 1, href: '/instance_admin/namespaces/1'};
const shared = makeSharedUi({capabilities: {instanceAdmin: true, namespaceAdmin: false, courseAdmin: false, canCreateCourses: true, canEditCourse: true}});
const users = [{id: 2, username: 'alice', firstName: 'Alice', lastName: 'A', instanceAdmin: false}, {id: 10, username: 'admin', firstName: 'Admin', lastName: 'B', instanceAdmin: true}];
const adminData = {action: '/instance_admin/panel', users, namespaces: [namespace], namespaceApiUrl: '/api/namespaces', namespacePanelUrlTemplate: '/instance_admin/namespaces/0', createCourseUrl: '/instance_admin/courses/new', courses: [
  {name: 'Math', href: '/instance_admin/courses/math/edit', namespaceSlug: 'study'},
  {name: 'Physics', href: '/instance_admin/courses/physics/edit', namespaceSlug: 'other'},
]};
const pageData = {namespace, users: [{id: 2, username: 'alice', rmsId: 42, role: 'namespace_admin'}], availableUsers: [{id: 10, username: 'bob', rmsId: 99}], courses: [{id: 4, name: 'Math', href: '/math', owners: 'alice', status: 'running', gitlabGroup: 'g/math', editHref: '/instance_admin/courses/Math/edit'}], usersUrl: '/api/namespaces/1/users', roles: [{value: 'namespace_admin', label: 'Namespace Admin'}, {value: 'program_manager', label: 'Program Manager'}, {value: 'student', label: 'Demote to Student'}], createCourseUrl: '/instance_admin/courses/new?namespace_id=1', namespacesUrl: '/instance_admin/namespaces'};
beforeEach(() => vi.stubGlobal('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}}));
afterEach(() => vi.unstubAllGlobals());

it('does not offer namespace mutation to an ordinary member', () => {
  renderUi(<NamespacesPage shared={makeSharedUi()} data={{namespaces: [namespace]}} />);
  expect(screen.getByRole('link', {name: 'Учебный'})).toHaveAttribute('href', '/instance_admin/namespaces/1');
  expect(screen.queryByRole('button', {name: 'Create namespace'})).not.toBeInTheDocument();
});

it.each([['Grant admin rights', 'alice', 'grant'], ['Revoke admin rights', 'admin', 'revoke']])('submits %s with native action, selected username and CSRF', async (label, username, action) => {
  const user = userEvent.setup();
  renderUi(<InstanceAdminPage shared={shared} data={adminData} />);
  await user.click(screen.getByRole('button', {name: label}));
  const dialog = screen.getByRole('dialog');
  await user.selectOptions(within(dialog).getByLabelText('Select user'), username);
  const form = dialog.querySelector('form')!;
  expect(form).toHaveAttribute('action', '/instance_admin/panel');
  expect(form).toHaveAttribute('method', 'post');
  expect(Object.fromEntries(new FormData(form))).toEqual({csrf_token: 'test-csrf', action, username});
});

it('edits another user profile through the existing native POST', async () => {
  const user = userEvent.setup();
  renderUi(<InstanceAdminPage shared={shared} data={adminData} />);
  await user.click(screen.getByRole('button', {name: 'Edit profile alice'}));
  const dialog = screen.getByRole('dialog');
  await user.clear(within(dialog).getByLabelText('First name'));
  await user.type(within(dialog).getByLabelText('First name'), 'Алиса');
  const form = dialog.querySelector('form')!;
  expect(form).toHaveAttribute('action', '/update_profile');
  expect(Object.fromEntries(new FormData(form))).toEqual({csrf_token: 'test-csrf', action: 'change', username: 'alice', first_name: 'Алиса', last_name: 'A'});
});

it('preserves instance course namespace filtering and numeric keyboard sorting', async () => {
  const user = userEvent.setup();
  renderUi(<InstanceAdminPage shared={shared} data={adminData} />);
  await user.selectOptions(screen.getByLabelText('Filter by namespace'), 'study');
  expect(screen.getByRole('link', {name: 'Math'})).toHaveAttribute('href', '/instance_admin/courses/math/edit');
  expect(screen.queryByRole('link', {name: 'Physics'})).not.toBeInTheDocument();
  const table = screen.getByRole('table', {name: 'Users'});
  const header = within(table).getByRole('button', {name: /ID/});
  header.focus();
  await user.keyboard('{Enter}');
  expect(within(table).getAllByRole('row').slice(1).map((row) => within(row).getAllByRole('cell')[0].textContent)).toEqual(['2', '10']);
  await user.keyboard('{Enter}');
  expect(within(table).getAllByRole('row').slice(1).map((row) => within(row).getAllByRole('cell')[0].textContent)).toEqual(['10', '2']);
});

it('creates a namespace with null description, preserving input on error and updating the visible list', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{"error":"Slug exists"}', {status: 409}))
    .mockResolvedValueOnce(new Response('{"id":8,"name":"New","slug":"new","description":null,"gitlab_group_id":88}', {status: 201}))
    .mockResolvedValueOnce(new Response('{"users":[{"user_id":10,"role":"namespace_admin"}]}'));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<InstanceAdminPage shared={shared} data={adminData} />);
  await user.click(screen.getByRole('button', {name: 'Create namespace'}));
  const dialog = screen.getByRole('dialog');
  await user.type(within(dialog).getByLabelText('Name'), 'New');
  await user.type(within(dialog).getByLabelText('Slug'), 'new');
  await user.click(within(dialog).getByRole('button', {name: 'Create'}));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Slug exists');
  expect(within(dialog).getByLabelText('Slug')).toHaveValue('new');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({name: 'New', slug: 'new', description: null});
  expect(fetcher.mock.calls[0][0]).toBe('/api/namespaces');
  expect(fetcher.mock.calls[0][1].headers.get('X-CSRFToken')).toBe('test-csrf');
  await user.click(within(dialog).getByRole('button', {name: 'Create'}));
  expect(await screen.findByRole('link', {name: 'New'})).toHaveAttribute('href', '/instance_admin/namespaces/8');
});

it('adds a user using POST-only roles and refreshes members, count and candidate availability', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValue(new Response('{"id":55,"user_id":10,"namespace_id":1,"role":"program_manager"}', {status: 201}));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<NamespacePage shared={shared} data={pageData} />);
  await user.click(screen.getByRole('button', {name: 'Add user'}));
  const dialog = screen.getByRole('dialog');
  expect(within(dialog).queryByRole('option', {name: 'Demote to Student'})).not.toBeInTheDocument();
  await user.selectOptions(within(dialog).getByLabelText('Select user'), 'bob');
  await user.selectOptions(within(dialog).getByLabelText('Role'), 'program_manager');
  await user.click(within(dialog).getByRole('button', {name: 'Assign role'}));
  expect(await screen.findByRole('cell', {name: 'bob'})).toBeInTheDocument();
  expect(screen.getByText('Users: 2')).toBeInTheDocument();
  expect(fetcher.mock.calls[0][0]).toBe('/api/namespaces/1/users');
  expect(fetcher.mock.calls[0][1].method).toBe('POST');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({username: 'bob', role: 'program_manager'});
  await user.click(screen.getByRole('button', {name: 'Add user'}));
  expect(within(screen.getByRole('dialog')).queryByRole('option', {name: 'bob'})).not.toBeInTheDocument();
});

it('keeps selected PATCH role on a 403 and retries to refresh the visible role', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{"error":"Forbidden role"}', {status: 403}))
    .mockResolvedValueOnce(new Response('{"success":true,"old_role":"namespace_admin","new_role":"program_manager","user_id":2}'));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<NamespacePage shared={shared} data={pageData} />);
  await user.click(screen.getByRole('button', {name: 'Change role alice'}));
  const dialog = screen.getByRole('dialog');
  await user.selectOptions(within(dialog).getByLabelText('Role'), 'program_manager');
  await user.click(within(dialog).getByRole('button', {name: 'Save role'}));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Forbidden role');
  expect(within(dialog).getByLabelText('Role')).toHaveValue('program_manager');
  expect(fetcher.mock.calls[0][0]).toBe('/api/namespaces/1/users/2');
  expect(fetcher.mock.calls[0][1].method).toBe('PATCH');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({role: 'program_manager'});
  await user.click(within(dialog).getByRole('button', {name: 'Save role'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByRole('cell', {name: 'Program Manager'})).toBeInTheDocument();
});

it.each(['Remove alice', 'Change role alice'])('confirms membership removal through %s and handles empty DELETE 204', async (action) => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValue(action === 'Remove alice' ? new Response(null, {status: 204}) : new Response('{"success":true,"new_role":"student","user_id":2}'));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<NamespacePage shared={shared} data={pageData} />);
  await user.click(screen.getByRole('button', {name: action}));
  const dialog = screen.getByRole('dialog');
  if (action === 'Change role alice') await user.selectOptions(within(dialog).getByLabelText('Role'), 'student');
  expect(fetcher).not.toHaveBeenCalled();
  expect(dialog).toHaveTextContent(/remove.*namespace/i);
  await user.click(within(dialog).getByRole('button', {name: action === 'Remove alice' ? 'Remove user' : 'Save role'}));
  await waitFor(() => expect(within(screen.getByRole('table', {name: 'Namespace users'})).queryByRole('cell', {name: 'alice'})).not.toBeInTheDocument());
  expect(screen.getByText('Users: 0')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(fetcher.mock.calls[0][0]).toBe('/api/namespaces/1/users/2');
  expect(fetcher.mock.calls[0][1].method).toBe(action === 'Remove alice' ? 'DELETE' : 'PATCH');
  if (action !== 'Remove alice') expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({role: 'student'});
});

it('retains namespace course details and native links', () => {
  renderUi(<NamespacePage shared={shared} data={pageData} />);
  expect(screen.getByRole('link', {name: 'Create course'})).toHaveAttribute('href', '/instance_admin/courses/new?namespace_id=1');
  expect(screen.getByRole('link', {name: 'Edit Math'})).toHaveAttribute('href', '/instance_admin/courses/Math/edit');
  expect(screen.getByRole('cell', {name: 'g/math'})).toBeInTheDocument();
  expect(screen.getByRole('cell', {name: 'running'})).toBeInTheDocument();
});

it('retries only the count read after successful creation and a failed refresh', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{"id":8,"name":"New","slug":"new","description":null,"gitlab_group_id":88}', {status: 201}))
    .mockResolvedValueOnce(new Response('{"error":"Offline"}', {status: 503}))
    .mockResolvedValueOnce(new Response('{"users":[{"user_id":10,"role":"namespace_admin"}]}'));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<InstanceAdminPage shared={shared} data={adminData} />);
  await user.click(screen.getByRole('button', {name: 'Create namespace'}));
  const dialog = screen.getByRole('dialog');
  await user.type(within(dialog).getByLabelText('Name'), 'New');
  await user.type(within(dialog).getByLabelText('Slug'), 'new');
  await user.click(within(dialog).getByRole('button', {name: 'Create'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Saved. Could not refresh member count');
  expect(screen.getByRole('link', {name: 'New'})).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Retry count refresh'}));
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  expect(fetcher.mock.calls.map(([url, init]) => [url, init.method ?? 'GET'])).toEqual([
    ['/api/namespaces', 'POST'], ['/api/namespaces/8/users', 'GET'], ['/api/namespaces/8/users', 'GET'],
  ]);
});

it('preserves add selections after error and permits a successful retry', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{"error":"RMS unavailable"}', {status: 500}))
    .mockResolvedValueOnce(new Response('{"id":55,"user_id":10,"namespace_id":1,"role":"namespace_admin"}', {status: 201}));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<NamespacePage shared={shared} data={pageData} />);
  await user.click(screen.getByRole('button', {name: 'Add user'}));
  const dialog = screen.getByRole('dialog');
  await user.selectOptions(within(dialog).getByLabelText('Select user'), 'bob');
  await user.selectOptions(within(dialog).getByLabelText('Role'), 'namespace_admin');
  await user.click(within(dialog).getByRole('button', {name: 'Assign role'}));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('RMS unavailable');
  expect(within(dialog).getByLabelText('Select user')).toHaveValue('bob');
  expect(within(dialog).getByLabelText('Role')).toHaveValue('namespace_admin');
  expect(screen.getByText('Users: 1')).toBeInTheDocument();
  await user.click(within(dialog).getByRole('button', {name: 'Assign role'}));
  expect(await screen.findByRole('cell', {name: '99'})).toBeInTheDocument();
  expect(screen.getByText('Users: 2')).toBeInTheDocument();
});

it('retains a member when removal fails, retries DELETE, and makes the removed member selectable again', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{"error":"Removal forbidden"}', {status: 403}))
    .mockResolvedValueOnce(new Response(null, {status: 204}));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<NamespacePage shared={shared} data={pageData} />);
  await user.click(screen.getByRole('button', {name: 'Remove alice'}));
  const dialog = screen.getByRole('dialog');
  await user.click(within(dialog).getByRole('button', {name: 'Remove user'}));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Removal forbidden');
  expect(screen.getByText('Users: 1')).toBeInTheDocument();
  await user.click(within(dialog).getByRole('button', {name: 'Remove user'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  await user.click(screen.getByRole('button', {name: 'Add user'}));
  expect(within(screen.getByRole('dialog')).getByRole('option', {name: 'alice'})).toBeInTheDocument();
});

it('assigns instance-selected namespace membership and refreshes its displayed count', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response('{"id":55,"user_id":2,"namespace_id":1,"role":"program_manager"}', {status: 201}))
    .mockResolvedValueOnce(new Response('{"users":[{"user_id":10,"role":"namespace_admin"},{"user_id":2,"role":"program_manager"}]}'));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<InstanceAdminPage shared={shared} data={adminData} />);
  await user.click(screen.getByRole('button', {name: 'Assign role in namespace'}));
  await user.selectOptions(screen.getByLabelText('Namespace'), '1');
  const dialog = screen.getByRole('dialog');
  await user.selectOptions(within(dialog).getByLabelText('Select user'), 'alice');
  await user.selectOptions(within(dialog).getByLabelText('Role'), 'program_manager');
  await user.click(within(dialog).getByRole('button', {name: 'Assign role'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(fetcher.mock.calls[0][0]).toBe('/api/namespaces/1/users');
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({username: 'alice', role: 'program_manager'});
  expect(within(screen.getByRole('table', {name: 'Namespaces'})).getByRole('cell', {name: '2'})).toBeInTheDocument();
});

it('sorts real string RMS IDs numerically without losing alphanumeric provider IDs', async () => {
  const user = userEvent.setup();
  renderUi(<NamespacePage shared={shared} data={{...pageData, users: [
    {id: 2, username: 'alice', rmsId: '100', role: 'namespace_admin'},
    {id: 10, username: 'bob', rmsId: '9', role: 'program_manager'},
    {id: 11, username: 'carol', rmsId: 'sourcecraft-id', role: 'program_manager'},
  ]}} />);
  const table = screen.getByRole('table', {name: 'Namespace users'});
  await user.click(within(table).getByRole('button', {name: 'RMS ID (GitLab)'}));
  expect(within(table).getAllByRole('row').slice(1).map((row) => within(row).getAllByRole('cell')[2].textContent)).toEqual(['9', '100', 'sourcecraft-id']);
});
