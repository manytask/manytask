import {screen, render, fireEvent, act} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, expect, it, vi} from 'vitest';

import {Theme} from './Theme';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('uses the existing theme key and responds to system changes in auto', async () => {
  let notify = (_event: MediaQueryListEvent) => {};
  let removed = false;
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value)});
  vi.stubGlobal('matchMedia', () => ({matches: false, addEventListener: (_name: string, listener: typeof notify) => {notify = listener;}, removeEventListener: () => {removed = true;}}));
  const user = userEvent.setup();
  const view = render(<Theme><div>content</div></Theme>);
  await user.click(screen.getByRole('button', {name: 'Dark Theme'}));
  expect(localStorage.getItem('theme')).toBe('dark');
  await user.click(screen.getByRole('button', {name: 'Auto Theme'}));
  act(() => notify({matches: true} as MediaQueryListEvent));
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  view.unmount();
  expect(removed).toBe(true);
});

it('continues to switch theme when storage throws', () => {
  vi.stubGlobal('localStorage', {getItem: () => {throw new Error('blocked');}, setItem: () => {throw new Error('blocked');}});
  render(<Theme><div>content</div></Theme>);
  fireEvent.click(screen.getByRole('button', {name: 'Dark Theme'}));
  expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
});
