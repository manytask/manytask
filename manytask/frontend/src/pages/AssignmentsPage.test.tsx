import {fireEvent, screen, waitFor, within} from '@testing-library/react';
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
  expect(screen.queryByText(/20\.12\.2025/)).not.toBeInTheDocument();
  expect(screen.getByText('Expired: 02.01.2026 00:00')).toHaveAttribute('title', 'UTC');
  await user.click(screen.getByRole('button', {name: 'Show past deadlines'}));
  expect(screen.getByText(/20\.12\.2025/)).toBeInTheDocument();
  expect(screen.queryByText('Expired: 02.01.2026 00:00')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Hide past deadlines'}));
  expect(screen.queryByText(/20\.12\.2025/)).not.toBeInTheDocument();
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

it('hides a duplicate single-task total and keeps totals that add information', () => {
  const groups: AssignmentsData['groups'] = [
    {...data.groups[0], name: 'Exact', earned: 4, maximum: 10, deadlines: [], graph: null,
      tasks: [{...data.groups[0].tasks[0], name: 'Only task', earned: 4, score: 10}]},
    {...data.groups[0], name: 'Bonus differs', earned: 4, maximum: 10, deadlines: [], graph: null,
      tasks: [{...data.groups[0].tasks[0], name: 'Bonus task', earned: 4, score: 4, bonus: true}]},
    {...data.groups[0], name: 'Several', earned: 7, maximum: 20, deadlines: [], graph: null,
      tasks: [
        {...data.groups[0].tasks[0], name: 'First', earned: 3, score: 10},
        {...data.groups[0].tasks[0], name: 'Second', earned: 4, score: 10},
      ]},
  ];
  renderUi(<AssignmentsPage shared={makeSharedUi()} data={{...data, groups}} />);

  expect(within(screen.getByRole('heading', {name: 'Exact'}).closest('article')!).queryByText('Total: 4/10')).not.toBeInTheDocument();
  expect(within(screen.getByRole('heading', {name: 'Bonus differs'}).closest('article')!).getByText('Total: 4/10')).toBeInTheDocument();
  expect(within(screen.getByRole('heading', {name: 'Several'}).closest('article')!).getByText('Total: 7/20')).toBeInTheDocument();
});

it('shows truthful deadline and submission labels', () => {
  const labelled: AssignmentsData = {...data, groups: [{...data.groups[0], expired: false, graph: null,
    deadlines: [{
      at: '2026-03-03T12:30:00Z', percent: 1, passed: false, urgent: false,
      remaining: 'Deadline expires in: 59 d.', progress: 1,
      date: '03.03.2026', time: '15:30', tz: 'MSK',
    }],
    tasks: [
      {...data.groups[0].tasks[0], name: 'Submitted task', statistics: 0.27},
      {...data.groups[0].tasks[0], name: 'No statistics', statistics: null},
    ],
  }]};
  renderUi(<AssignmentsPage shared={makeSharedUi()} data={labelled} />);

  expect(screen.getByText('100% of points until 03.03.2026 15:30 · 59 d. left')).toHaveAttribute('title', 'MSK');
  expect(screen.getByText('Submitted by 27%')).toBeInTheDocument();
  expect(screen.queryByText('Submitted by 0%')).not.toBeInTheDocument();
  expect(screen.queryByText('Active')).not.toBeInTheDocument();
  expect(screen.getByRole('progressbar', {name: 'Time elapsed until 03.03.2026 15:30'}))
    .toHaveAttribute('aria-valuenow', '1');
});

it('keeps future score steps visible and puts one dated timer on the current interval', async () => {
  const stepped: AssignmentsData = {...data, groups: [{...data.groups[0], expired: false, graph: null,
    deadlines: [
      {at: '2026-01-01T12:00:00Z', percent: 1, passed: true, urgent: false, remaining: '', progress: 100,
        date: '01.01.2026', time: '15:00', tz: 'MSK'},
      {at: '2026-01-06T12:00:00Z', percent: 0.7, passed: false, urgent: false,
        remaining: 'Deadline expires in: 3 d.', progress: 40, date: '06.01.2026', time: '15:00', tz: 'MSK'},
      {at: '2026-01-13T12:00:00Z', percent: 0.5, passed: false, urgent: false,
        remaining: 'Deadline expires in: 10 d.', progress: 0, date: '13.01.2026', time: '15:00', tz: 'MSK'},
    ],
  }]};
  const user = userEvent.setup();
  renderUi(<AssignmentsPage shared={makeSharedUi()} data={stepped} />);

  expect(screen.queryByText(/100% of points until 01\.01\.2026/)).not.toBeInTheDocument();
  const current = screen.getByText('70% of points until 06.01.2026 15:00 · 3 d. left');
  expect(current.closest('.assignment-deadline')).toHaveAttribute('aria-current', 'step');
  expect(screen.getByText('50% of points until 13.01.2026 15:00 · 10 d. left')).toBeInTheDocument();
  expect(screen.getByRole('progressbar', {name: 'Time elapsed until 06.01.2026 15:00'}))
    .toHaveAttribute('aria-valuenow', '40');
  expect(screen.getAllByRole('progressbar', {name: /Time elapsed until/})).toHaveLength(1);

  await user.click(screen.getByRole('button', {name: 'Show past deadlines'}));
  expect(screen.getByText('100% of points until 01.01.2026 15:00 · Expired')).toBeInTheDocument();
  expect(screen.getByText('50% of points until 13.01.2026 15:00 · 10 d. left')).toBeInTheDocument();
  expect(screen.getAllByRole('progressbar', {name: /Time elapsed until/})).toHaveLength(1);
});

it('counts completion from solved task states and handles empty groups', () => {
  const groups: AssignmentsData['groups'] = [
    {...data.groups[0], name: 'Mixed', earned: -8, maximum: 10, deadlines: [], graph: null,
      tasks: [
        {...data.groups[0].tasks[0], name: 'Solved', state: 'solved', earned: -10},
        {...data.groups[0].tasks[0], name: 'Over solved bonus', state: 'over_solved', earned: 2, bonus: true},
        {...data.groups[0].tasks[0], name: 'Partial', state: 'partial', earned: 9},
        {...data.groups[0].tasks[0], name: 'Unsolved', state: 'unsolved', earned: 0},
      ]},
    {...data.groups[1], name: 'Empty', tasks: []},
  ];
  renderUi(<AssignmentsPage shared={makeSharedUi()} data={{...data, groups}} />);

  const mixed = screen.getByRole('heading', {name: 'Mixed'}).closest('article')!;
  const empty = screen.getByRole('heading', {name: 'Empty'}).closest('article')!;
  expect(within(mixed).getByRole('progressbar', {name: 'Task completion'})).toHaveAttribute('aria-valuenow', '50');
  expect(screen.getByText('2 of 4 tasks completed')).toBeInTheDocument();
  expect(within(empty).getByRole('progressbar', {name: 'Task completion'})).toHaveAttribute('aria-valuenow', '0');
  expect(document.body).not.toHaveTextContent('NaN');
});

it('mounts the deadline graph only while its disclosure is open and disconnects resize', async () => {
  const disconnect = vi.fn();
  let observes = 0;
  vi.stubGlobal('ResizeObserver', class {
    observe() { observes++; }
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
  const user = userEvent.setup();
  const disclosure = screen.getByText('Current multiplier: 75%');
  expect(screen.getByText('Next deadline in: 3 h.')).toBeInTheDocument();
  expect(screen.queryByRole('img', {name: 'Deadline score curve'})).not.toBeInTheDocument();
  expect(observes).toBe(0);

  await user.click(disclosure);
  // Native details toggle is asynchronous; the canvas can mount before its
  // passive effect has drawn the curve and subscribed to size changes.
  const canvas = await screen.findByRole('img', {name: 'Deadline score curve'});
  await waitFor(() => expect(observes).toBe(1));
  fireEvent.mouseMove(canvas, {clientX: 38, clientY: 7});
  expect(screen.getByRole('tooltip')).toHaveTextContent('01.01.2026 12:00 MSK');
  fireEvent.mouseLeave(canvas);
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();

  await user.click(disclosure);
  await waitFor(() => {
    expect(screen.queryByRole('img', {name: 'Deadline score curve'})).not.toBeInTheDocument();
    expect(disconnect).toHaveBeenCalledOnce();
  });
  view.unmount();
  expect(disconnect).toHaveBeenCalledOnce();
});
