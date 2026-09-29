import {expect, it} from 'vitest';
import {orderGroups, taskOrderKey} from './taskOrder';

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
