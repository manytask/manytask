import {act, render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, expect, it, vi} from 'vitest';

import {Theme} from '../app/Theme';
import {DeadlineGraph, type DeadlineGraphData} from './DeadlineGraph';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it('repaints the curve with CSS colors after explicit and automatic theme changes', async () => {
  const colors: string[] = [];
  const context: Partial<CanvasRenderingContext2D> = {
    setTransform() {}, clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {},
    stroke() { if (context.lineWidth === 2) colors.push(String(context.strokeStyle)); },
    closePath() {}, fill() {}, fillText() {}, setLineDash() {}, arc() {},
    measureText: () => ({width: 20} as TextMetrics),
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as CanvasRenderingContext2D);
  const actualComputedStyle = window.getComputedStyle;
  vi.spyOn(window, 'getComputedStyle').mockImplementation((element) => {
    const original = actualComputedStyle(element);
    return {...original, fontFamily: 'Arial', getPropertyValue: (name: string) => {
      if (name === '--graph-line') return document.body.classList.contains('g-root_theme_dark') ? '#eeeeee' : '#111111';
      return original.getPropertyValue(name);
    }} as CSSStyleDeclaration;
  });

  vi.stubGlobal('localStorage', {getItem: () => null, setItem() {}});
  let activeObservers = 0;
  vi.stubGlobal('ResizeObserver', class {
    observe() { activeObservers++; }
    disconnect() { activeObservers--; }
  });
  let systemChange = (_event: MediaQueryListEvent) => {};
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addEventListener: (_type: string, callback: typeof systemChange) => { systemChange = callback; },
    removeEventListener() {},
  }));
  const graph: DeadlineGraphData = {
    status: 'active', percent: 0.75, hint: 'Next deadline in: 3 h.',
    points: [
      {ts: 100, pct: 1, label: 'Start', date: '01.01.2026', time: '12:00', tz: 'MSK'},
      {ts: 200, pct: 0.5, label: 'End', date: '02.01.2026', time: '12:00', tz: 'MSK'},
      {ts: 200, pct: 0, label: '', date: '02.01.2026', time: '12:00', tz: 'MSK'},
    ],
  };

  const view = render(<Theme><DeadlineGraph graph={graph} now="1970-01-01T00:02:30Z" /></Theme>);
  expect(colors.at(-1)).toBe('#111111');
  expect(activeObservers).toBe(1);

  const user = userEvent.setup();
  await user.click(screen.getByRole('button', {name: 'Dark Theme'}));
  expect(colors.at(-1)).toBe('#eeeeee');
  expect(activeObservers).toBe(1);

  await user.click(screen.getByRole('button', {name: 'Auto Theme'}));
  expect(colors.at(-1)).toBe('#111111');
  expect(activeObservers).toBe(1);

  act(() => systemChange({matches: true} as MediaQueryListEvent));
  expect(colors.at(-1)).toBe('#eeeeee');
  expect(activeObservers).toBe(1);
  view.unmount();
  expect(activeObservers).toBe(0);
});
