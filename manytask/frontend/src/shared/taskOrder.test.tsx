import {act, renderHook} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {orderGroups, taskOrderKey, useTaskOrder} from './taskOrder';

it('sorts instants and keeps equal dates stable without mutating input', () => {
  const groups = [
    {name: '__proto__', start: '2026-01-01T03:00:00+03:00'},
    {name: '10', start: '2026-01-01T00:00:00Z'},
    {name: '2', start: '2025-12-31T22:00:00Z'},
  ];
  expect(orderGroups(groups, 'asc').map((x) => x.name)).toEqual(['2', '__proto__', '10']);
  expect(orderGroups(groups, 'desc').map((x) => x.name)).toEqual(['__proto__', '10', '2']);
  expect(groups.map((x) => x.name)).toEqual(['__proto__', '10', '2']);
  expect(taskOrderKey('a.b', '__proto__')).toBe('manytask:task-group-order:["a.b","__proto__"]');
});

afterEach(() => vi.unstubAllGlobals());

it('ignores invalid saved order and isolates preferences by course', () => {
  const saved = new Map([[taskOrderKey('alice', 'Python'), 'invalid']]);
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => saved.get(key) ?? null,
    setItem: (key: string, value: string) => saved.set(key, value),
  });
  const first = renderHook(() => useTaskOrder('alice', 'Python'));
  expect(first.result.current[0]).toBe('desc');
  act(() => first.result.current[1]());
  expect(first.result.current[0]).toBe('asc');
  first.unmount();
  const same = renderHook(() => useTaskOrder('alice', 'Python'));
  expect(same.result.current[0]).toBe('asc');
  same.unmount();
  const other = renderHook(() => useTaskOrder('alice', 'C++'));
  expect(other.result.current[0]).toBe('desc');
});
