import {screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {expect, it} from 'vitest';

import {makeSharedUi, renderUi} from '../test/render';
import {AppShell} from './AppShell';

it('shows navigation, course stats, flashes, and profile action', async () => {
  const user = userEvent.setup();
  renderUi(<AppShell shared={makeSharedUi({username: 'alice', firstName: 'Alice', lastName: 'Example', navigation: [{label: 'Assignments', href: '/python'}], courses: [{label: 'python', href: '/python'}], flashes: [{category: 'error', message: 'Retry'}], course: {name: 'python', status: 'started', score: 65, bonusScore: 5, maxStartedScore: 100}})}><div>page content</div></AppShell>);
  expect(screen.getByRole('navigation', {name: 'Main navigation'})).toHaveTextContent('Assignments');
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

it('shows a zero score and zero started maximum', () => {
  renderUi(<AppShell shared={makeSharedUi({course: {name: 'python', status: 'started', score: 0, bonusScore: 0, maxStartedScore: 0}})}><div>course</div></AppShell>);
  expect(screen.getByLabelText('Course score')).toHaveTextContent('0.0% · 0/0');
});
