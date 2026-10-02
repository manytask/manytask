import {screen} from '@testing-library/react';
import {afterEach, expect, it} from 'vitest';

import {makeSharedUi, renderUi} from '../test/render';
import {App} from './App';

function setPage(page: string, data: unknown, schema_version = 1) {
  const script = document.createElement('script');
  script.id = 'manytask-page';
  script.type = 'application/json';
  script.textContent = JSON.stringify({schema_version, page, data, shared: makeSharedUi()});
  document.body.append(script);
}
afterEach(() => document.getElementById('manytask-page')?.remove());

it('keeps the shell visible while loading the requested page, then renders its actions', async () => {
  setPage('not-ready', {courseName: 'Python', links: [{label: 'Refresh course', href: '/python'}]});
  renderUi(<App />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading page');
  expect(screen.getByRole('navigation', {name: 'Main navigation'})).toBeVisible();
  expect(screen.getByRole('navigation', {name: 'Breadcrumb'})).toHaveTextContent('Course not ready');
  expect(await screen.findByRole('link', {name: 'Refresh course'})).toHaveAttribute('href', '/python');
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

it.each(['signup', 'signup-finish', 'create-project'])('loads the %s form from the shared auth page', async (page) => {
  setPage(page, {kind: page, action: '/auth', values: {}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false});
  renderUi(<App />);
  const submit = await screen.findByRole('button', {name: /Finish registration|Sign up|Join course/});
  expect(submit.closest('form')).toHaveAttribute('action', '/auth');
});

it('explains incompatible data before attempting a page load', () => {
  setPage('not-ready', {}, 2);
  renderUi(<App />);
  expect(screen.getByRole('alert')).toHaveTextContent('Incompatible page version');
});

it('explains unsupported pages inside the shell', () => {
  setPage('unknown', {});
  renderUi(<App />);
  expect(screen.getByRole('alert')).toHaveTextContent('not supported');
});

it('loads the Yandex signup variant with its login link', async () => {
  setPage('signup-yandex-id', {kind: 'signup-yandex-id', loginUrl: '/login'});
  renderUi(<App />);
  expect(await screen.findByRole('link', {name: 'Login with Yandex ID'})).toHaveAttribute('href', '/login');
});
