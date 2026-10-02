import {afterEach, expect, it, vi} from 'vitest';
import {requestJson} from './requestJson';
afterEach(() => vi.unstubAllGlobals());
it('sends credentials, CSRF and JSON headers while preserving options', async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response('{"success":true}'));
  vi.stubGlobal('fetch', fetcher);
  await expect(requestJson('/save', 'csrf', {method: 'POST', body: '{}', headers: {'X-Test': 'value'}})).resolves.toEqual({success: true});
  const init = fetcher.mock.calls[0][1];
  expect(init.credentials).toBe('same-origin');
  expect(init.method).toBe('POST');
  expect(init.headers.get('X-CSRFToken')).toBe('csrf');
  expect(init.headers.get('Content-Type')).toBe('application/json');
  expect(init.headers.get('X-Test')).toBe('value');
});
it.each([[400, {message: 'Bad score'}, 'Bad score'], [403, {error: 'Forbidden'}, 'Forbidden'], [200, {success: false, message: 'Not saved'}, 'Not saved'], [500, {}, 'Request failed (500)']])('rejects HTTP/application errors %s', async (status, body, message) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), {status})));
  await expect(requestJson('/save', '')).rejects.toThrow(message);
});
it('accepts empty DELETE 204 and propagates network and invalid JSON failures', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(new Response(null, {status: 204})).mockRejectedValueOnce(new Error('Offline')).mockResolvedValueOnce(new Response('<html>')));
  await expect(requestJson<void>('/remove', '', {method: 'DELETE'})).resolves.toBeUndefined();
  await expect(requestJson('/save', '')).rejects.toThrow('Offline');
  await expect(requestJson('/save', '')).rejects.toThrow();
});
