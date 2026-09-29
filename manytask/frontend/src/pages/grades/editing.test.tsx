import {screen, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach, beforeEach, expect, it, vi} from 'vitest';
import {makeSharedUi, renderUi} from '../../test/render';
import {GradesPage} from './GradesPage';
import type {GradesData, GradesResponse, StudentRow} from './types';

const shared = makeSharedUi({username: 'teacher'});
const page: GradesData = {courseName: 'Python', canEdit: true, readOnlyFields: ['username', 'total_score'], urls: {database: '/database', updateScore: '/score', updateComment: '/comment', overrideGrade: '/grade', clearGradeOverride: '/clear'}};
const student: StudentRow = {username: 'alice', scores: {'part.one': 3, bonus_score: 0}, first_name: 'Alice', last_name: 'A', total_score: 3, percent: 30, large_count: 1, grade: 5, grade_is_override: true, comment: 'old'};
const response: GradesResponse = {tasks: [{group: 'old', name: 'part.one', group_start: '2026-01-01', score: 10}], students: [student]};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {status});

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class {observe() {} unobserve() {} disconnect() {}});
  const stored = new Map<string, string>();
  vi.stubGlobal('localStorage', {getItem: (key: string) => stored.get(key) ?? null, setItem: (key: string, value: string) => {stored.set(key, value);}});
});
afterEach(() => {vi.restoreAllMocks(); vi.unstubAllGlobals();});

it('keeps a zero score draft after 500, retries its exact request, and reloads without resetting the view', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(json(response)).mockResolvedValueOnce(json({success: false, message: 'Try again'}, 500))
    .mockResolvedValueOnce(json({success: true})).mockResolvedValueOnce(json({...response, students: [{...student, scores: {...student.scores, 'part.one': 0}, total_score: 0, percent: 0}]}));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<GradesPage shared={shared} data={page} />);
  await screen.findByText('alice');
  await user.type(screen.getByRole('textbox', {name: 'Search students'}), 'alice');
  await user.click(screen.getByRole('button', {name: 'Edit score part.one for alice'}));
  const dialog = screen.getByRole('dialog');
  const input = within(dialog).getByRole('spinbutton', {name: 'Score'});
  await user.clear(input);
  await user.type(input, '0');
  await user.click(within(dialog).getByRole('button', {name: 'Save'}));
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('Try again');
  expect(input).toHaveValue(0);
  await user.click(within(dialog).getByRole('button', {name: 'Save'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(screen.getByRole('textbox', {name: 'Search students'})).toHaveValue('alice');
  expect(screen.getByRole('button', {name: 'Edit score part.one for alice'})).toHaveTextContent('0');
  for (const call of [fetcher.mock.calls[1], fetcher.mock.calls[2]]) {
    expect(call[0]).toBe('/score');
    expect(call[1].method).toBe('POST');
    expect(call[1].headers.get('X-CSRFToken')).toBe('test-csrf');
    expect(JSON.parse(call[1].body)).toEqual({row_data: student, new_scores: {'part.one': 0}});
  }
});

it('sends a negative score, comment and integer override; clear requires confirmation', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(json(response)));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<GradesPage shared={shared} data={page} />);
  await screen.findByText('alice');
  await user.click(screen.getByRole('button', {name: 'Edit score part.one for alice'}));
  await user.clear(screen.getByRole('spinbutton', {name: 'Score'}));
  await user.type(screen.getByRole('spinbutton', {name: 'Score'}), '-2');
  await user.click(screen.getByRole('dialog').querySelector('button[type="submit"]')!);
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(JSON.parse(fetcher.mock.calls[1][1].body).new_scores).toEqual({'part.one': -2});

  await user.click(screen.getByRole('button', {name: 'Edit comment for alice'}));
  await user.clear(screen.getByRole('textbox', {name: 'Comment'}));
  await user.type(screen.getByRole('textbox', {name: 'Comment'}), ' new, "note"{enter}');
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Save'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(JSON.parse(fetcher.mock.calls[3][1].body)).toEqual({username: 'alice', comment: ' new, "note"\n'});

  await user.click(screen.getByRole('button', {name: 'Edit grade for alice'}));
  await user.clear(screen.getByRole('spinbutton', {name: 'Grade'}));
  await user.type(screen.getByRole('spinbutton', {name: 'Grade'}), '2.5');
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Save'}));
  expect(fetcher).toHaveBeenCalledTimes(5);
  expect(within(screen.getByRole('dialog')).getByRole('alert')).toHaveTextContent('integer');
  await user.clear(screen.getByRole('spinbutton', {name: 'Grade'}));
  await user.type(screen.getByRole('spinbutton', {name: 'Grade'}), '0');
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Save'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(JSON.parse(fetcher.mock.calls[5][1].body)).toEqual({username: 'alice', grade: 0});

  await user.click(screen.getByRole('button', {name: 'Edit grade for alice'}));
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Clear override'}));
  expect(fetcher).toHaveBeenCalledTimes(7);
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Confirm clear override'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(fetcher.mock.calls[7][0]).toBe('/clear');
  expect(JSON.parse(fetcher.mock.calls[7][1].body)).toEqual({username: 'alice'});
});

it('retries only the refresh after a successful write when reloading fails', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockResolvedValueOnce(json(response)).mockResolvedValueOnce(json({success: true}))
    .mockResolvedValueOnce(json({message: 'Database unavailable'}, 503))
    .mockResolvedValueOnce(json({...response, students: [{...student, scores: {...student.scores, 'part.one': 0}}]}));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<GradesPage shared={shared} data={page} />);
  await screen.findByText('alice');
  await user.click(screen.getByRole('button', {name: 'Edit score part.one for alice'}));
  const input = screen.getByRole('spinbutton', {name: 'Score'});
  await user.clear(input);
  await user.type(input, '0');
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Save'}));
  expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('Score saved, but refresh failed: Database unavailable');
  expect(input).toBeDisabled();
  expect(screen.getByRole('button', {name: 'Edit score part.one for alice'})).toHaveTextContent('3');
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Retry refresh'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(fetcher.mock.calls.map(([url]) => url)).toEqual(['/database', '/score', '/database', '/database']);
  expect(screen.getByRole('button', {name: 'Edit score part.one for alice'})).toHaveTextContent('0');
});

it('omits edit actions for a viewer', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(json(response))));
  renderUi(<GradesPage shared={shared} data={{...page, canEdit: false}} />);
  await screen.findByText('alice');
  expect(screen.queryByRole('button', {name: /Edit (score|comment|grade)/})).not.toBeInTheDocument();
});

it('edits bonus scores and omits actions for read-only task fields', async () => {
  const user = userEvent.setup();
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(json(response)));
  vi.stubGlobal('fetch', fetcher);
  renderUi(<GradesPage shared={shared} data={{...page, readOnlyFields: [...page.readOnlyFields, 'scores.part.one']}} />);
  await screen.findByText('alice');
  expect(screen.queryByRole('button', {name: 'Edit score part.one for alice'})).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', {name: 'Edit score bonus_score for alice'}));
  await user.clear(screen.getByRole('spinbutton', {name: 'Score'}));
  await user.type(screen.getByRole('spinbutton', {name: 'Score'}), '-1');
  await user.click(within(screen.getByRole('dialog')).getByRole('button', {name: 'Save'}));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(fetcher.mock.calls[1][0]).toBe('/score');
  expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({row_data: student, new_scores: {bonus_score: -1}});
});

it('exports every loaded row using visible legacy field labels and collapsed sums', async () => {
  const user = userEvent.setup();
  const rows = Array.from({length: 230}, (_, index) => ({...student, username: `student${index}`, scores: {'part.one': index === 229 ? -2 : 0, bonus_score: 0}}));
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(json({...response, students: rows}))));
  const create = vi.fn().mockReturnValue('blob:grades');
  const revoke = vi.fn();
  const clicked = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  vi.stubGlobal('URL', {...URL, createObjectURL: create, revokeObjectURL: revoke});
  renderUi(<GradesPage shared={shared} data={page} />);
  await screen.findByText('student0');
  await user.click(screen.getByRole('button', {name: 'Hide personal info'}));
  await user.click(screen.getByRole('button', {name: 'Collapse old'}));
  await user.click(screen.getByRole('button', {name: 'Download CSV'}));
  const csv = await create.mock.calls[0][0].text();
  expect(csv.split('\r\n')).toHaveLength(231);
  expect(csv.split('\r\n')[0]).toBe('rownum,username,grade,total_score,percent,large_count,scores.bonus_score,old_collapsed');
  expect(csv).toContain('student229');
  expect(csv).toContain('student229,5,3,30,1,0,-2');
  expect(csv).not.toContain('first_name');
  expect(csv).not.toContain('comment');
  expect(revoke).toHaveBeenCalledWith('blob:grades');
  expect(clicked).toHaveBeenCalledOnce();
});
