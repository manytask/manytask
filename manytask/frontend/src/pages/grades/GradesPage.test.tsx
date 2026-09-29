import {act, screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {makeSharedUi, renderUi} from '../../test/render';
import {GradesPage} from './GradesPage';
import type {GradesData, GradesResponse} from './types';

const shared = makeSharedUi({username: 'teacher'});
const data: GradesData = {courseName: 'Python', canEdit: true, readOnlyFields: ['username', 'total_score'], urls: {database: '/database', updateScore: '/score', updateComment: '/comment', overrideGrade: '/grade', clearGradeOverride: '/clear'}};
const response: GradesResponse = {
  tasks: [
    {group: 'old', name: 'part.one', group_start: '2026-01-01', score: 0},
    {group: 'old', name: 'negative', group_start: '2026-01-01', score: 0},
    {group: 'new', name: 'zero', group_start: '2026-02-01', score: 0},
  ],
  students: Array.from({length: 230}, (_, i) => ({username: `student${String(i).padStart(3, '0')}`, first_name: i < 220 ? 'Иван' : 'Other', last_name: 'Иванов', total_score: i, percent: 12.34, large_count: 2, grade: 7, grade_is_override: true, scores: {'part.one': 9, negative: -2, zero: 0, bonus_score: 5}, comment: 'Review', is_admin: i === 229})),
  max_score: 1000,
};
const rows = () => Array.from(screen.getByRole('table').querySelectorAll('tbody tr'));
const cells = (row: Element) => within(row as HTMLElement).getAllByRole('cell').map((cell) => cell.textContent);

beforeEach(() => {
  // jsdom has no layout; pointer/width behavior is covered by the browser suite.
  vi.stubGlobal('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}});
  const stored = new Map<string, string>();
  vi.stubGlobal('localStorage', {getItem: (key: string) => stored.get(key) ?? null, setItem: (key: string, value: string) => {stored.set(key, value);}});
});
afterEach(() => vi.unstubAllGlobals());

it('preserves filtering, page, hidden columns, two collapsed groups and sorting through group order changes and reload', async () => {
  const user = userEvent.setup();
  const refreshed = {...response, students: response.students.map((student) => ({...student, percent: 23.45}))};
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(response))).mockResolvedValueOnce(new Response(JSON.stringify(refreshed))));
  renderUi(<GradesPage shared={shared} data={data} />);
  await screen.findByText('student229');
  expect(rows()).toHaveLength(100);
  expect(rows()[0]).toHaveClass('grades-admin-row');
  expect(cells(rows()[0])).toEqual(['1', 'student229', 'Other', 'Иванов', '7 *', '229', '12.3', '2', '5', 'Review', '0', '9', '-2']);
  await user.type(screen.getByRole('textbox', {name: 'Search students'}), 'ivan ivanov');
  expect(screen.getByText('220 students')).toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Next page'}));
  expect(cells(rows()[0])[1]).toBe('student119');
  await user.click(screen.getByRole('button', {name: 'Collapse old'}));
  await user.click(screen.getByRole('button', {name: 'Collapse new'}));
  await user.click(screen.getByRole('button', {name: 'Hide personal info'}));
  screen.getByRole('button', {name: 'Username'}).focus();
  await user.keyboard('{Enter}');
  expect(cells(rows()[0])).toEqual(['101', 'student100', '7 *', '100', '12.3', '2', '5', '0', '7']);
  await user.click(screen.getByRole('button', {name: 'Show oldest first'}));
  expect(cells(rows()[0])).toEqual(['101', 'student100', '7 *', '100', '12.3', '2', '5', '7', '0']);
  await user.click(screen.getByRole('button', {name: 'Show newest first'}));
  await user.click(screen.getByRole('button', {name: 'Reload grades'}));
  await waitFor(() => expect(screen.getByRole('button', {name: 'Reload grades'})).toBeEnabled());
  expect(cells(rows()[0])).toEqual(['101', 'student100', '7 *', '100', '23.4', '2', '5', '0', '7']);
  expect(screen.queryByRole('button', {name: 'First Name'})).not.toBeInTheDocument();
  expect(screen.queryByRole('button', {name: 'Comment'})).not.toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Expand old'})).toBeInTheDocument();
  expect(screen.getByRole('textbox', {name: 'Search students'})).toHaveValue('ivan ivanov');
  await user.click(screen.getByRole('button', {name: 'Expand old'}));
  expect(cells(rows()[0]).slice(-2)).toEqual(['9', '-2']);
  await user.clear(screen.getByRole('textbox', {name: 'Search students'}));
  await user.type(screen.getByRole('textbox', {name: 'Search students'}), 'student229');
  expect(cells(rows()[0])[1]).toBe('student229');
  expect(screen.getByText('Page 1 of 1')).toBeInTheDocument();
}, 20000);

it('can filter before loading, retry failures, hide admins, and change page sizes including all', async () => {
  const user = userEvent.setup();
  let resolve!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn().mockReturnValueOnce(new Promise((done) => {resolve = done;})).mockResolvedValueOnce(new Response(JSON.stringify(response))));
  renderUi(<GradesPage shared={shared} data={data} />);
  await user.click(screen.getByRole('button', {name: 'Hide admins'}));
  await user.type(screen.getByRole('textbox', {name: 'Search students'}), 'student');
  await act(async () => resolve(new Response('{"error":"Unavailable"}', {status: 503})));
  expect(await screen.findByRole('alert')).toHaveTextContent('Unavailable');
  await user.click(screen.getByRole('button', {name: 'Retry'}));
  await screen.findByText('student228');
  expect(screen.queryByText('student229')).not.toBeInTheDocument();
  await user.selectOptions(screen.getByRole('combobox', {name: 'Rows per page'}), '25');
  expect(rows()).toHaveLength(25);
  await user.selectOptions(screen.getByRole('combobox', {name: 'Rows per page'}), 'all');
  expect(rows()).toHaveLength(229);
});

it('handles empty responses and omits admin-only columns and controls for viewers', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"tasks":[],"students":[]}')));
  renderUi(<GradesPage shared={shared} data={{...data, canEdit: false}} />);
  expect(await screen.findByText('No students found')).toBeInTheDocument();
  expect(screen.queryByRole('button', {name: 'Hide admins'})).not.toBeInTheDocument();
  expect(screen.queryByRole('button', {name: 'Comment'})).not.toBeInTheDocument();
});
