import {fireEvent, screen, within, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';

import {makeSharedUi, renderUi} from '../../test/render';
import {CreateCoursePage} from './CreateCoursePage';
import {EditCoursePage} from './EditCoursePage';
import {CourseAccess} from './CourseAccess';
import type {CourseFormData} from './types';

const base: CourseFormData = {
  action: '/instance_admin/courses/new', mode: 'create', rms: 'gitlab', labels: {}, values: {},
  namespaces: [{id: 4, name: 'Science', path: 'science'}], statuses: [], showAllScores: true,
  accessUrls: null,
};

beforeEach(() => vi.stubGlobal('ResizeObserver', class {
  observe() {}
  unobserve() {}
  disconnect() {}
}));
afterEach(() => vi.unstubAllGlobals());

it('submits the native create fields and a permitted namespace zero', () => {
  renderUi(<CreateCoursePage shared={makeSharedUi()} data={{...base, namespaces: []}} />);
  const form = screen.getByRole('button', {name: 'Create course'}).closest('form')!;
  expect(form.action).toContain('/instance_admin/courses/new');
  expect(form.method).toBe('post');
  const fields = new FormData(form);
  expect(fields.get('csrf_token')).toBe('test-csrf');
  expect(fields.get('namespace_id')).toBe('0');
  for (const name of ['unique_course_name', 'registration_secret', 'token', 'course_group',
    'course_public_repo', 'course_students_group', 'default_branch']) {
    expect(fields.has(name)).toBe(true);
  }
  expect(fields.get('default_branch')).toBe('main');
  expect(fields.get('show_allscores')).toBe('on');
});

it('keeps edit field names and the immutable token', () => {
  const values = {registration_secret: 'course-secret', token: 'server-token', course_status: 'in_progress',
    gitlab_course_group: 'course', gitlab_course_public_repo: 'course/public',
    gitlab_course_students_group: 'course/students', gitlab_default_branch: 'main'};
  renderUi(<EditCoursePage shared={makeSharedUi()} data={{...base, action: '/instance_admin/courses/c/edit',
    mode: 'edit', values, statuses: [{value: 'in_progress', label: 'In Progress'}]}} />);
  const form = screen.getByRole('button', {name: 'Save changes'}).closest('form')!;
  const fields = new FormData(form);
  expect(fields.get('gitlab_default_branch')).toBe('main');
  expect(fields.get('course_status')).toBe('in_progress');
  expect(fields.get('show_allscores')).toBe('on');
  expect(fields.has('token')).toBe(false);
  expect(screen.getByLabelText('Course Token')).toBeDisabled();
  expect(screen.queryByRole('button', {name: /program manager/i})).not.toBeInTheDocument();
});

it('preserves SourceCraft hidden group values and an error response input', () => {
  renderUi(<EditCoursePage shared={makeSharedUi({errorMessage: 'CSRF Error'})} data={{...base,
    mode: 'edit', rms: 'sourcecraft', values: {gitlab_course_group: 'stored-group', registration_secret: 'draft-secret'}}} />);
  expect(screen.getByRole('alert')).toHaveTextContent('CSRF Error');
  const form = screen.getByRole('button', {name: 'Save changes'}).closest('form')!;
  expect(new FormData(form).get('gitlab_course_group')).toBe('stored-group');
  expect(screen.getByLabelText('Registration Secret')).toHaveValue('draft-secret');
});

it('suggests namespace and semester paths without replacing edited repository fields', async () => {
  const user = userEvent.setup();
  renderUi(<CreateCoursePage shared={makeSharedUi()} data={{...base, values: {namespace_id: '4'}}} />);
  await user.type(screen.getByLabelText('Course Group'), 'math');
  expect(screen.getByLabelText('Public Repo')).toHaveValue('science/math/public-2026-fall');
  expect(screen.getByLabelText('Students Group')).toHaveValue('science/math/students-2026-fall');
  await user.clear(screen.getByLabelText('Public Repo'));
  await user.type(screen.getByLabelText('Public Repo'), 'custom/public');
  await user.type(screen.getByLabelText('Course Group'), '2');
  expect(screen.getByLabelText('Public Repo')).toHaveValue('custom/public');
  expect(screen.getByLabelText('Students Group')).toHaveValue('science/math2/students-2026-fall');
  const form = screen.getByRole('button', {name: 'Create course'}).closest('form')!;
  expect(new FormData(form).get('namespace_id')).toBe('4');
  expect(fireEvent.submit(form)).toBe(false);
  expect(screen.getByRole('alert')).toHaveTextContent('Repository paths must begin');
});

it('accepts an explicit full group path in the selected namespace', async () => {
  const user = userEvent.setup();
  renderUi(<CreateCoursePage shared={makeSharedUi()} data={{...base, values: {namespace_id: '4'}}} />);
  await user.type(screen.getByLabelText('Course Group'), 'science/math');
  expect(screen.getByLabelText('Public Repo')).toHaveValue('science/math/public-2026-fall');
  const form = screen.getByRole('button', {name: 'Create course'}).closest('form')!;
  expect(fireEvent.submit(form)).toBe(true);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('blocks create when namespace paths could not be loaded', async () => {
  const user = userEvent.setup();
  renderUi(<CreateCoursePage shared={makeSharedUi()} data={{...base,
    namespaces: [], namespaceError: 'Could not load namespace paths. Please refresh the page.'}} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Could not load namespace paths');
  await user.type(screen.getByLabelText('Course Group'), 'math');
  const form = screen.getByRole('button', {name: 'Create course'}).closest('form')!;
  expect(fireEvent.submit(form)).toBe(false);
});

it('posts grant and revoke bodies and reloads real access rows', async () => {
  const requests: Array<{url: string; body: string | null}> = [];
  let admin = false;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    requests.push({url, body: init?.body as string ?? null});
    if (init?.method === 'POST') admin = JSON.parse(init.body as string).is_admin;
    return {ok: true, status: 200, json: async () => ({users: admin ? [{username: 'alice', first_name: 'Alice', last_name: 'A', access_levels: ['course_admin']}] : []})};
  }));
  const user = userEvent.setup();
  renderUi(<CourseAccess urls={{users: '/api/c/access_users', courseAdmin: '/api/c/course_admin'}}
    csrfToken="csrf" candidates={[{username: 'alice', firstName: 'Alice', lastName: 'A'}]} />);
  await waitFor(() => expect(requests).toHaveLength(1));
  await user.click(screen.getByRole('button', {name: 'Grant course admin rights'}));
  await user.selectOptions(screen.getByLabelText('Select new course admin'), 'alice');
  await user.click(screen.getByRole('button', {name: 'Grant rights'}));
  await waitFor(() => expect(screen.getByRole('button', {name: 'Revoke course admin rights from alice'})).toBeInTheDocument());
  expect(requests[1]).toEqual({url: '/api/c/course_admin', body: '{"username":"alice","is_admin":true}'});
  await user.click(screen.getByRole('button', {name: 'Revoke course admin rights from alice'}));
  await waitFor(() => expect(requests[3]).toEqual({url: '/api/c/course_admin', body: '{"username":"alice","is_admin":false}'}));
});

it('keeps selected grant target when the server rejects a change', async () => {
  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => init?.method === 'POST'
    ? {ok: false, status: 404, json: async () => ({error: 'User not enrolled'})}
    : {ok: true, status: 200, json: async () => ({users: []})}));
  const user = userEvent.setup();
  renderUi(<CourseAccess urls={{users: '/users', courseAdmin: '/admin'}} csrfToken="csrf"
    candidates={[{username: 'alice', firstName: 'Alice', lastName: 'A'}]} />);
  await user.click(screen.getByRole('button', {name: 'Grant course admin rights'}));
  await user.selectOptions(screen.getByLabelText('Select new course admin'), 'alice');
  await user.click(screen.getByRole('button', {name: 'Grant rights'}));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('User not enrolled'));
  expect(screen.getByLabelText('Select new course admin')).toHaveValue('alice');
});
