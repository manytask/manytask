import type {StudentRow} from './types';

export function csvCell(value: unknown): string {
  const text = value == null ? '' : String(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function exportGradesCsv(rows: readonly StudentRow[], columns: readonly {header: string; value: (row: StudentRow) => unknown}[]): string {
  return [columns.map((column) => csvCell(column.header)).join(','),
    ...rows.map((row) => columns.map((column) => csvCell(column.value(row))).join(','))].join('\r\n');
}
