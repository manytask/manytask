import {screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, expect, it, vi} from 'vitest';

import {makeSharedUi, renderUi} from '../test/render';
import {AppShell} from './AppShell';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

it('shows authorized navigation, course context, flashes, and profile action', async () => {
  const user = userEvent.setup();
  renderUi(<AppShell page="assignments" shared={makeSharedUi({username: 'alice', firstName: 'Alice', lastName: 'Example', navigation: [{label: 'Courses', href: '/'}, {label: 'Assignments', href: '/python'}, {label: 'All Scores', href: '/python/database'}], courses: [{label: 'python', href: '/python'}, {label: 'algorithms', href: '/algorithms'}], flashes: [{category: 'error', message: 'Retry'}], course: {name: 'python', status: 'started', score: 65, bonusScore: 5, maxStartedScore: 100}})}><div>page content</div></AppShell>);
  const navigation = screen.getByRole('navigation', {name: 'Main navigation'});
  expect(navigation).toHaveTextContent('Assignments');
  expect(screen.getByRole('link', {name: 'Assignments'})).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('link', {name: 'All Scores'})).not.toHaveAttribute('aria-current');
  expect(screen.getByRole('navigation', {name: 'Breadcrumb'})).toHaveTextContent('Manytask/python/Assignments');
  expect(screen.getByText('algorithms').closest('a')).toHaveAttribute('href', '/algorithms');
  expect(screen.getByText('Retry')).toBeInTheDocument();
  expect(screen.getByLabelText('Course score')).toHaveTextContent('65.0% · 60+5/100');
  expect(screen.getByText('page content')).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Change user info'}));
  const dialog = await screen.findByRole('dialog');
  expect(dialog).toContainElement(screen.getByLabelText('First name'));
  const form = screen.getByRole('button', {name: 'Save'}).closest('form')!;
  const data = new FormData(form);
  expect(form.getAttribute('action')).toBe('/update_profile');
  expect(data.get('action')).toBe('change');
  expect(data.get('username')).toBe('alice');
  expect(data.get('csrf_token')).toBe('test-csrf');
  await user.keyboard('{Escape}');
  expect(screen.getByRole('button', {name: 'Change user info'})).toHaveFocus();
});

it('persists a compact sidebar and restores it on the next mount', async () => {
  const user = userEvent.setup();
  const shared = makeSharedUi({navigation: [{label: 'Courses', href: '/'}]});
  const first = renderUi(<AppShell page="courses" shared={shared}><div>courses</div></AppShell>);
  await user.click(screen.getByRole('button', {name: 'Collapse navigation'}));
  expect(localStorage.getItem('manytask.sidebarCollapsed')).toBe('true');
  first.unmount();

  renderUi(<AppShell page="courses" shared={shared}><div>courses</div></AppShell>);
  expect(screen.getByRole('button', {name: 'Expand navigation'})).toBeVisible();
  expect(screen.getByRole('link', {name: 'Courses'})).toBeVisible();
});

it('keeps collapse controls usable when storage is blocked', async () => {
  vi.stubGlobal('localStorage', {getItem: () => {throw new Error('blocked');}, setItem: () => {throw new Error('blocked');}});
  const user = userEvent.setup();
  renderUi(<AppShell page="courses" shared={makeSharedUi()}><div>courses</div></AppShell>);
  await user.click(screen.getByRole('button', {name: 'Collapse navigation'}));
  expect(screen.getByRole('button', {name: 'Expand navigation'})).toBeVisible();
});

it('closes the mobile drawer with Escape and returns focus to its opener', async () => {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query === '(max-width: 899px)', media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }));
  const user = userEvent.setup();
  renderUi(<AppShell page="courses" shared={makeSharedUi({navigation: [{label: 'Courses', href: '/'}]})}><div>courses</div></AppShell>);
  const opener = screen.getByRole('button', {name: 'Open navigation'});
  await user.click(opener);
  const drawer = screen.getByRole('dialog', {name: 'Navigation'});
  expect(drawer).toBeVisible();
  expect(screen.getByRole('button', {name: 'Close navigation'})).toHaveFocus();
  within(drawer).getByRole('link', {name: 'Sign out'}).focus();
  await user.tab();
  expect(within(drawer).getByRole('link', {name: 'Manytask'})).toHaveFocus();
  const profileOpener = within(drawer).getByRole('button', {name: 'Change user info'});
  await user.click(profileOpener);
  expect(screen.getByLabelText('First name')).toBeVisible();
  await user.keyboard('{Escape}');
  await waitFor(() => expect(screen.queryByLabelText('First name')).not.toBeInTheDocument());
  expect(drawer).toBeVisible();
  expect(profileOpener).toHaveFocus();
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('dialog', {name: 'Navigation'})).not.toBeInTheDocument();
  expect(opener).toHaveFocus();
});

it('shows a zero score and zero started maximum', () => {
  renderUi(<AppShell page="assignments" shared={makeSharedUi({course: {name: 'python', status: 'started', score: 0, bonusScore: 0, maxStartedScore: 0}})}><div>course</div></AppShell>);
  expect(screen.getByLabelText('Course score')).toHaveTextContent('0.0% · 0/0');
});

it('shows the ADMIN indicator only for course administrators', () => {
  const base = makeSharedUi();
  const {rerender} = renderUi(<AppShell page="assignments" shared={{...base, capabilities: {...base.capabilities, courseAdmin: true}}}><p>course</p></AppShell>);
  expect(screen.getByText('ADMIN')).toBeVisible();
  rerender(<AppShell page="assignments" shared={base}><p>course</p></AppShell>);
  expect(screen.queryByText('ADMIN')).not.toBeInTheDocument();
});
