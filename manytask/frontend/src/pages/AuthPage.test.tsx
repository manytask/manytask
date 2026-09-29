import {fireEvent, screen} from '@testing-library/react';
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

it('accepts ordinary signup values and rejects whitespace in constrained fields', () => {
  renderUi(<AuthPage shared={makeSharedUi()} data={{kind: 'signup', action: '/signup', values: {}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false}} />);
  for (const [label, valid, invalid] of [
    ['Username', 'alice', 'alice smith'],
    ['First name', 'Alice', 'Alice Smith'],
    ['Last name', 'Smith', 'Smith Jones'],
    ['Password', 'secret123', 'secret word'],
    ['Re-type password', 'secret123', 'secret word'],
  ]) {
    const input = screen.getByLabelText(label, {exact: true}) as HTMLInputElement;
    fireEvent.change(input, {target: {value: valid}});
    expect(input.checkValidity(), `${label} should accept ${valid}`).toBe(true);
    fireEvent.change(input, {target: {value: invalid}});
    expect(input.checkValidity(), `${label} should reject spaces`).toBe(false);
  }
  const email = screen.getByLabelText('Email address') as HTMLInputElement;
  expect(email.getAttribute('pattern')).toBe(String.raw`[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}`);
  fireEvent.change(email, {target: {value: 'alice@example.com'}});
  expect(email.checkValidity()).toBe(true);
  fireEvent.change(email, {target: {value: 'invalid'}});
  expect(email.checkValidity()).toBe(false);
  fireEvent.change(email, {target: {value: 'alice@exampleXcom'}});
  expect(email.checkValidity()).toBe(false);
});

it('accepts ordinary names on registration finish', () => {
  renderUi(<AuthPage shared={makeSharedUi()} data={{kind: 'signup-finish', action: '/signup_finish', values: {}, loginUrl: '/login', sourcecraftUrl: null, invitationRequired: false}} />);
  for (const label of ['First name', 'Last name']) {
    const input = screen.getByLabelText(label) as HTMLInputElement;
    fireEvent.change(input, {target: {value: 'Smith'}});
    expect(input.checkValidity()).toBe(true);
    fireEvent.change(input, {target: {value: 'Smith Jones'}});
    expect(input.checkValidity()).toBe(false);
  }
});
