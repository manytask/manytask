import {screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {expect, it} from 'vitest';

import {makeSharedUi, renderUi} from '../test/render';
import {AuthPage} from './AuthPage';

it('submits the existing signup contract without returning a password value', () => {
  renderUi(<AuthPage shared={makeSharedUi()} data={{kind: 'signup', action: '/signup', values: {username: 'alice'}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false}} />);
  const form = screen.getByRole('button', {name: 'Sign up'}).closest('form')!;
  const data = new FormData(form);
  expect(form.getAttribute('method')).toBe('post');
  expect(data.get('csrf_token')).toBe('test-csrf');
  expect(data.get('username')).toBe('alice');
  expect([...data.keys()].sort()).toEqual(['csrf_token', 'email', 'firstname', 'lastname', 'password', 'password2', 'username']);
  expect(data.get('password')).toBe('');
});

it('blocks submission when confirmation differs, including Enter submission', async () => {
  const user = userEvent.setup();
  renderUi(<AuthPage shared={makeSharedUi()} data={{kind: 'signup', action: '/signup', values: {}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false}} />);
  await user.type(screen.getByLabelText('Username'), 'alice');
  await user.type(screen.getByLabelText('First name'), 'Alice');
  await user.type(screen.getByLabelText('Last name'), 'Example');
  await user.type(screen.getByLabelText('Email address'), 'alice@example.com');
  await user.type(screen.getByLabelText('Password', {exact: true}), 'password123');
  await user.type(screen.getByLabelText('Re-type password'), 'different{enter}');
  expect(screen.getByRole('alert')).toHaveTextContent("Passwords don't match");
});

it('renders the Yandex ID login link without a local password form', () => {
  renderUi(<AuthPage shared={makeSharedUi()} data={{kind: 'signup-yandex-id', action: '/signup', values: {}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false}} />);
  expect(screen.getByRole('link', {name: /Yandex ID/})).toHaveAttribute('href', '/login');
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
});

it('keeps the SourceCraft account recovery link visible', () => {
  renderUi(<AuthPage shared={makeSharedUi({errorMessage: 'SourceCraft account required'})} data={{kind: 'signup-finish', action: '/signup_finish', values: {}, loginUrl: '/login', sourcecraftUrl: 'https://sourcecraft.example/register', invitationRequired: false, sourcecraftNotRegistered: true}} />);
  expect(screen.getByRole('link', {name: 'Register on SourceCraft'})).toHaveAttribute('href', 'https://sourcecraft.example/register');
});

it('keeps the finish and enrollment form field names', () => {
  const shared = makeSharedUi();
  const finish = renderUi(<AuthPage shared={shared} data={{kind: 'signup-finish', action: '/signup_finish', values: {firstname: 'Alice'}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false}} />);
  const finishForm = screen.getByRole('button', {name: 'Finish registration'}).closest('form')!;
  expect(finishForm.getAttribute('action')).toBe('/signup_finish');
  expect([...new FormData(finishForm).keys()].sort()).toEqual(['csrf_token', 'firstname', 'lastname']);
  expect(new FormData(finishForm).get('firstname')).toBe('Alice');
  finish.unmount();

  renderUi(<AuthPage shared={shared} data={{kind: 'create-project', action: '/python/create_project', values: {}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false}} />);
  const projectForm = screen.getByRole('button', {name: 'Join course'}).closest('form')!;
  expect(projectForm.getAttribute('action')).toBe('/python/create_project');
  expect([...new FormData(projectForm).keys()].sort()).toEqual(['csrf_token', 'secret']);
});
