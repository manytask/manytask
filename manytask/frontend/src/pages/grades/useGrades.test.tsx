import {act, renderHook, waitFor} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {useGrades} from './useGrades';

afterEach(() => vi.unstubAllGlobals());
it('aborts on URL changes and unmount and ignores late responses', async () => {
  const pending: Array<{resolve: (value: Response) => void; signal: AbortSignal}> = [];
  vi.stubGlobal('fetch', vi.fn((_url, init) => new Promise<Response>((resolve) => pending.push({resolve, signal: init.signal}))));
  const {result, rerender, unmount} = renderHook(({url}) => useGrades(url), {initialProps: {url: '/one'}});
  rerender({url: '/two'});
  expect(pending[0].signal.aborted).toBe(true);
  await act(async () => pending[1].resolve(new Response('{"tasks":[],"students":[],"max_score":2}')));
  await waitFor(() => expect(result.current.data?.max_score).toBe(2));
  await act(async () => pending[0].resolve(new Response('{"tasks":[],"students":[],"max_score":1}')));
  expect(result.current.data?.max_score).toBe(2);
  act(() => {void result.current.reload();});
  unmount();
  expect(pending[2].signal.aborted).toBe(true);
  await act(async () => pending[2].resolve(new Response('{"tasks":[],"students":[]}')));
});
