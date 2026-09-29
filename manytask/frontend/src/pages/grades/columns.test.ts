import {expect, it} from 'vitest';
import {buildColumns, taskColumnId, groupColumnId, groupTotalColumnId} from './columns';
import type {ColumnDef} from '@gravity-ui/table/tanstack';
import type {StudentRow, TaskMeta} from './types';

it('keeps prototype, numeric and dotted names distinct and accesses the full task name', () => {
  const tasks: TaskMeta[] = [
    {name: 'part.one', group: '__proto__', group_start: '2026-01-01', score: 0},
    {name: 'same', group: '10', group_start: '2026-01-02', score: 0},
    {name: 'same', group: '2', group_start: '2026-01-03', score: 0},
    {name: '__proto__', group: '__proto__', group_start: '2026-01-01', score: 0},
  ];
  const columns = buildColumns(tasks, false, 'asc', new Set(), () => {});
  const groups = columns.filter((col) => 'columns' in col);
  expect(groups.map((col) => col.id)).toEqual([groupColumnId('__proto__'), groupColumnId('10'), groupColumnId('2')]);
  const leaves = groups.flatMap((col) => (col as {columns: ColumnDef<StudentRow>[]}).columns);
  expect(new Set(leaves.map((col) => col.id)).size).toBe(7);
  expect(taskColumnId(tasks[0])).toBe('["task","__proto__","part.one"]');
  const row = {scores: JSON.parse('{"part.one":-3,"same":0,"__proto__":7}')} as StudentRow;
  const read = (id: string) => {
    const col = leaves.find((col) => col.id === id)!;
    return 'accessorFn' in col ? col.accessorFn!(row, 0) : undefined;
  };
  expect(read(taskColumnId(tasks[0]))).toBe(-3);
  expect(read(taskColumnId(tasks[1]))).toBe(0);
  expect(read(taskColumnId(tasks[3]))).toBe(7);
  expect(read(groupTotalColumnId('__proto__'))).toBe(4);
});
