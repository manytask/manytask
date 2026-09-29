import {expect, it} from 'vitest';
import {csvCell, exportGradesCsv} from './csv';
import type {StudentRow} from './types';

it('preserves zero, negative values, commas, quotes and newlines', () => {
  expect(csvCell(0)).toBe('0');
  expect(csvCell(-2)).toBe('-2');
  expect(csvCell('a,"b"\nc')).toBe('"a,""b""\nc"');
  expect(csvCell(null)).toBe('');
});

it('writes a hand checked CSV with escaped headers and values', () => {
  const rows: StudentRow[] = [{username: 'a,"b"\nc', scores: {task: -2}, total_score: -2, percent: 0, large_count: 0, grade: null}];
  expect(exportGradesCsv(rows, [
    {header: 'username', value: (row) => row.username},
    {header: 'scores.task', value: (row) => row.scores.task},
  ])).toBe('username,scores.task\r\n"a,""b""\nc",-2');
});
