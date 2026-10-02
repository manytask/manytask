/** Shared client for existing same-origin JSON endpoints. */
export async function requestJson<T>(url: string, csrfToken: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (csrfToken) headers.set('X-CSRFToken', csrfToken);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(url, {...init, headers, credentials: 'same-origin'});
  if (response.status === 204 && response.ok) return undefined as T;
  const body = await response.json();
  if (!response.ok || body?.success === false) {
    throw new Error(body?.message || body?.error || `Request failed (${response.status})`);
  }
  return body as T;
}
