import {fireEvent, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';

import {makeSharedUi, renderUi} from '../test/render';
import {AssignmentsPage, type AssignmentsData} from './AssignmentsPage';

const data: AssignmentsData = {
  courseName: 'C', now: '2026-01-03T00:00:00Z', sourcecraftInviteUrl: null,
  groups: [
    {name: 'Older', start: '2025-12-01T00:00:00Z', end: '2026-01-02T00:00:00Z', endDate: '02.01.2026', endTime: '00:00', endTz: 'UTC', expired: true, special: false, earned: 0, maximum: 10,
      tasks: [{name: '__proto__', url: 'https://example.org/task', score: 10, earned: 0, bonus: false, special: false, state: 'unsolved', statistics: 0}],
      deadlines: [{at: '2025-12-20T00:00:00Z', percent: 0.5, passed: true, urgent: false, remaining: '', progress: 100, date: '20.12.2025', time: '00:00', tz: 'UTC'}], graph: null},
    {name: 'Newer', start: '2025-12-20T00:00:00Z', end: '2026-02-01T00:00:00Z', endDate: '01.02.2026', endTime: '00:00', endTz: 'UTC', expired: false, special: false, earned: 0, maximum: 0,
      tasks: [], deadlines: [], graph: null},
  ],
};

const stored = new Map<string, string>();
beforeEach(() => {
  stored.clear();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => { stored.set(key, value); },
  });
});
afterEach(() => vi.unstubAllGlobals());

function groupNames() {
  return within(screen.getByRole('region', {name: 'Assignment groups'})).getAllByRole('heading', {level: 2}).map((node) => node.textContent);
}

it('toggles order by click, Space and Enter, then loads it for the same user and course only', async () => {
  const user = userEvent.setup();
  const shared = makeSharedUi({username: 'alice'});
  const view = renderUi(<AssignmentsPage shared={shared} data={data} />);
  expect(groupNames()).toEqual(['Newer', 'Older']);
  const order = screen.getByRole('button', {name: 'Show oldest first'});
  await user.click(order);
  expect(groupNames()).toEqual(['Older', 'Newer']);
  expect(order).toHaveTextContent('Show newest first');
  order.focus();
  await user.keyboard(' ');
  expect(groupNames()).toEqual(['Newer', 'Older']);
  await user.keyboard('{Enter}');
  expect(groupNames()).toEqual(['Older', 'Newer']);
  expect(order.className).toBe(screen.getByRole('button', {name: 'Show past deadlines'}).className);
  view.unmount();
  const same = renderUi(<AssignmentsPage shared={shared} data={data} />);
  expect(groupNames()).toEqual(['Older', 'Newer']);
  same.unmount();
  renderUi(<AssignmentsPage shared={makeSharedUi({username: 'bob'})} data={data} />);
  expect(groupNames()).toEqual(['Newer', 'Older']);
});

it('keeps ordering in memory when storage throws and reveals passed deadlines', async () => {
  vi.stubGlobal('localStorage', {getItem: () => { throw Error('blocked'); }, setItem: () => { throw Error('blocked'); }});
  const user = userEvent.setup();
  renderUi(<AssignmentsPage shared={makeSharedUi()} data={data} />);
  expect(screen.queryByText('20.12.2025')).not.toBeInTheDocument();
  expect(screen.getByText('Expired: 02.01.2026 00:00')).toHaveAttribute('title', 'UTC');
  await user.click(screen.getByRole('button', {name: 'Show past deadlines'}));
  expect(screen.getByText('20.12.2025')).toBeInTheDocument();
  expect(screen.queryByText('Expired: 02.01.2026 00:00')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Hide past deadlines'}));
  expect(screen.queryByText('20.12.2025')).not.toBeInTheDocument();
  expect(screen.getByText('Expired: 02.01.2026 00:00')).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Show oldest first'}));
  expect(groupNames()).toEqual(['Older', 'Newer']);
  expect(screen.getByRole('link', {name: /__proto__/})).toHaveAttribute('href', 'https://example.org/task');
});

it('shows an empty course without stale group controls', () => {
  renderUi(<AssignmentsPage shared={makeSharedUi()} data={{...data, groups: []}} />);
  expect(screen.getByText('No assignments yet.')).toBeInTheDocument();
});

it('keeps the SourceCraft invitation action', () => {
  const url = 'https://sourcecraft.dev/me/organizations';
  renderUi(<AssignmentsPage shared={makeSharedUi()} data={{...data, sourcecraftInviteUrl: url}} />);
  expect(screen.getByRole('link', {name: url})).toHaveAttribute('href', url);
});

it('shows server breakpoint date, time and timezone in the graph tooltip and disconnects resize', () => {
  const disconnect = vi.fn();
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    disconnect() { disconnect(); }
  });
  const draw = vi.fn();
  const canvasContext = {
    setTransform: draw, clearRect: draw, beginPath: draw, moveTo: draw, lineTo: draw,
    stroke: draw, closePath: draw, fill: draw, fillText: draw, setLineDash: draw, arc: draw,
    measureText: () => ({width: 20}),
  } as unknown as CanvasRenderingContext2D;
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(canvasContext);
  const graphData: AssignmentsData = {...data, groups: [{...data.groups[0], deadlines: [], graph: {
    status: 'active', percent: 0.75, hint: 'Next deadline in: 3 h.',
    points: [
      {ts: 100, pct: 1, label: '01.01', date: '01.01.2026', time: '12:00', tz: 'MSK'},
      {ts: 200, pct: 0.5, label: '02.01', date: '02.01.2026', time: '12:00', tz: 'MSK'},
      {ts: 200, pct: 0, label: '', date: '02.01.2026', time: '12:00', tz: 'MSK'},
    ],
  }}]};
  const view = renderUi(<AssignmentsPage shared={makeSharedUi()} data={graphData} />);
  const canvas = screen.getByRole('img', {name: 'Deadline score curve'});
  expect(screen.getByText('Next deadline in: 3 h.')).toBeInTheDocument();
  fireEvent.mouseMove(canvas, {clientX: 38, clientY: 7});
  expect(screen.getByRole('tooltip')).toHaveTextContent('01.01.2026 12:00 MSK');
  fireEvent.mouseLeave(canvas);
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  view.unmount();
  expect(disconnect).toHaveBeenCalledOnce();
});
