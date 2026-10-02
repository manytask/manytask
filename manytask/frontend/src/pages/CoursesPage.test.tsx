import {fireEvent, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';

import {makeSharedUi, renderUi} from '../test/render';
import {CoursesPage, type CoursesData} from './CoursesPage';

const data: CoursesData = {
  courses: [
    {name: 'Иван', status: 'active', href: '/ivan', owners: '', namespaceSlug: 'physics', editHref: null},
    {name: 'Math', status: 'finished', href: '/math', owners: '', namespaceSlug: 'algebra', editHref: null},
    {name: 'Python', status: 'created', href: '/python', owners: '', namespaceSlug: 'computer-science', editHref: '/instance_admin/courses/python/edit'},
  ],
  statusOrder: ['created', 'active', 'finished'],
  adminNamespaces: [{id: 4, name: 'Applied science', href: '/instance_admin/namespaces/4', slug: 'science', description: 'Research', coursesCount: 2, usersCount: 5}],
  createCourseUrl: '/instance_admin/courses/new',
  instanceAdminUrl: '/instance_admin/panel',
  namespacesUrl: '/instance_admin/namespaces',
};

const stored = new Map<string, string>();
beforeEach(() => {
  stored.clear();
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => stored.set(key, value),
  });
});
afterEach(() => vi.unstubAllGlobals());

it('shows unfinished courses, toggles completed courses and keeps permitted admin links', async () => {
  const user = userEvent.setup();
  renderUi(<CoursesPage shared={makeSharedUi()} data={data} />);
  expect(screen.getByRole('link', {name: 'Иван'})).toHaveAttribute('href', '/ivan');
  expect(screen.queryByRole('link', {name: 'Math'})).not.toBeInTheDocument();
  expect(screen.getByRole('link', {name: 'Create course'})).toHaveAttribute('href', data.createCourseUrl);
  expect(screen.getByRole('link', {name: 'Applied science'})).toHaveAttribute('href', '/instance_admin/namespaces/4');
  await user.click(screen.getByRole('button', {name: 'Show completed courses'}));
  expect(screen.getByRole('link', {name: 'Math'})).toHaveAttribute('href', '/math');
  await user.click(screen.getByRole('button', {name: 'Hide completed courses'}));
  expect(screen.queryByRole('link', {name: 'Math'})).not.toBeInTheDocument();
});

it('combines table search and status filter, including wrong keyboard layout', async () => {
  const user = userEvent.setup();
  renderUi(<CoursesPage shared={makeSharedUi()} data={data} />);
  await user.click(screen.getByRole('button', {name: 'Table view'}));
  const table = screen.getByRole('table', {name: 'Courses'});
  expect(within(table).getAllByRole('row')).toHaveLength(4);
  await user.type(screen.getByRole('textbox', {name: 'Search courses'}), 'bdfy');
  expect(within(table).getAllByRole('row')).toHaveLength(2);
  expect(within(table).getByRole('link', {name: 'Иван'})).toBeInTheDocument();
  await user.click(screen.getByRole('combobox', {name: 'Course status'}));
  await user.click(screen.getByRole('option', {name: 'finished'}));
  expect(within(table).queryByRole('link', {name: 'Иван'})).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Clear'}));
  expect(within(table).getAllByRole('row')).toHaveLength(4);
  await user.type(screen.getByRole('textbox', {name: 'Search courses'}), 'algebra');
  expect(within(table).getByRole('link', {name: 'Math'})).toBeInTheDocument();
  expect(within(table).getAllByRole('row')).toHaveLength(2);
});

it('orders the status menu by the server lifecycle and leaves unknown statuses last', async () => {
  const user = userEvent.setup();
  renderUi(<CoursesPage shared={makeSharedUi()} data={{
    ...data,
    courses: [...data.courses, {name: 'Extra', status: 'custom', href: '/extra', owners: '', namespaceSlug: '', editHref: null}],
  }} />);
  await user.click(screen.getByRole('button', {name: 'Table view'}));
  await user.click(screen.getByRole('combobox', {name: 'Course status'}));
  expect(screen.getAllByRole('option').map((option) => option.textContent?.trim())).toEqual([
    'All statuses', 'created', 'active', 'finished', 'custom',
  ]);
});

it('persists table choice and survives blocked storage', async () => {
  const user = userEvent.setup();
  const first = renderUi(<CoursesPage shared={makeSharedUi()} data={data} />);
  await user.click(screen.getByRole('button', {name: 'Table view'}));
  expect(localStorage.getItem('manytask.coursesView')).toBe('table');
  first.unmount();
  const second = renderUi(<CoursesPage shared={makeSharedUi()} data={data} />);
  expect(screen.getByRole('table', {name: 'Courses'})).toBeInTheDocument();
  second.unmount();
  vi.stubGlobal('localStorage', {
    getItem: () => { throw new Error('blocked'); },
    setItem: () => { throw new Error('blocked'); },
  });
  renderUi(<CoursesPage shared={makeSharedUi()} data={data} />);
  expect(screen.getByRole('button', {name: 'Table view'})).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Table view'}));
  expect(screen.getByRole('table', {name: 'Courses'})).toBeInTheDocument();
});

it('uses the previous course URL for trimmed enrollment input', async () => {
  const user = userEvent.setup();
  renderUi(<CoursesPage shared={makeSharedUi()} data={{...data, adminNamespaces: [], createCourseUrl: null, instanceAdminUrl: null, namespacesUrl: null}} />);
  expect(screen.queryByRole('link', {name: 'Create course'})).not.toBeInTheDocument();
  const input = screen.getByRole('textbox', {name: 'Register on new course'});
  await user.type(input, '  sample-course  ');
  const form = screen.getByRole('button', {name: 'Go'}).closest('form')!;
  fireEvent.submit(form);
  expect(form.getAttribute('action')).toBe('/sample-course');
});

function firstColumn(table: HTMLElement): string[] {
  return within(table).getAllByRole('row').slice(1).map((row) => within(row).getAllByRole('cell')[0].textContent!.trim());
}

it('sorts course rows by namespace with blanks last and by server status order', async () => {
  const user = userEvent.setup();
  renderUi(<CoursesPage shared={makeSharedUi()} data={{...data, courses: [
    {name: 'Bravo', status: 'created', href: '/bravo', owners: '', namespaceSlug: '', editHref: null},
    {name: 'Alpha', status: 'finished', href: '/alpha', owners: '', namespaceSlug: 'zeta', editHref: null},
    {name: 'Charlie', status: 'active', href: '/charlie', owners: '', namespaceSlug: 'alpha', editHref: null},
  ]}} />);
  await user.click(screen.getByRole('button', {name: 'Table view'}));
  const table = screen.getByRole('table', {name: 'Courses'});
  expect(firstColumn(table)).toEqual(['Alpha', 'Bravo', 'Charlie']);
  await user.click(within(table).getByRole('button', {name: 'Namespace'}));
  expect(firstColumn(table)).toEqual(['Charlie', 'Alpha', 'Bravo']);
  await user.click(within(table).getByRole('button', {name: 'Namespace'}));
  expect(firstColumn(table)).toEqual(['Alpha', 'Charlie', 'Bravo']);
  await user.click(within(table).getByRole('button', {name: 'Status'}));
  expect(firstColumn(table)).toEqual(['Bravo', 'Charlie', 'Alpha']);
  await user.type(screen.getByRole('textbox', {name: 'Search courses'}), 'alpha');
  expect(firstColumn(table)).toEqual(['Charlie', 'Alpha']);
  await user.click(screen.getByRole('button', {name: 'Clear'}));
  expect(firstColumn(table)).toEqual(['Bravo', 'Charlie', 'Alpha']);
  await user.click(within(table).getByRole('button', {name: 'Name'}));
  expect(firstColumn(table)).toEqual(['Alpha', 'Bravo', 'Charlie']);
  await user.click(within(table).getByRole('button', {name: 'Name'}));
  expect(firstColumn(table)).toEqual(['Charlie', 'Bravo', 'Alpha']);
});

it('sorts administered namespaces by name initially and numeric counts from keyboard headers', async () => {
  const user = userEvent.setup();
  renderUi(<CoursesPage shared={makeSharedUi()} data={{...data, adminNamespaces: [
    {id: 1, name: 'Beta', href: '/ns/1', slug: 'b', description: '', coursesCount: 10, usersCount: 2},
    {id: 2, name: 'Gamma', href: '/ns/2', slug: 'g', description: '', coursesCount: 1, usersCount: 20},
    {id: 3, name: 'Alpha', href: '/ns/3', slug: 'a', description: '', coursesCount: 2, usersCount: 3},
  ]}} />);
  const table = screen.getByRole('table', {name: 'Admin namespaces'});
  expect(firstColumn(table)).toEqual(['Alpha', 'Beta', 'Gamma']);
  const coursesHeader = within(table).getByRole('button', {name: 'Courses'});
  coursesHeader.focus();
  await user.keyboard('{Enter}');
  expect(firstColumn(table)).toEqual(['Gamma', 'Alpha', 'Beta']);
  await user.click(within(table).getByRole('button', {name: 'Courses'}));
  expect(firstColumn(table)).toEqual(['Beta', 'Alpha', 'Gamma']);
  await user.click(within(table).getByRole('button', {name: 'Users'}));
  expect(firstColumn(table)).toEqual(['Beta', 'Alpha', 'Gamma']);
  await user.click(within(table).getByRole('button', {name: 'Users'}));
  expect(firstColumn(table)).toEqual(['Gamma', 'Alpha', 'Beta']);
});
