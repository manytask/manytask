import {Button} from '@gravity-ui/uikit';
import type {ColumnDef} from '@gravity-ui/table/tanstack';
import {orderGroups, type TaskOrder} from '../../shared/taskOrder';
import type {StudentRow, TaskMeta} from './types';

export const taskColumnId = (task: TaskMeta) => JSON.stringify(['task', task.group, task.name]);
export const groupColumnId = (name: string) => JSON.stringify(['group', name]);
export const groupTotalColumnId = (name: string) => JSON.stringify(['group-total', name]);
export const personalColumns = ['first_name', 'last_name', 'comment'];
export const pinnedColumns = ['rownum', 'username', 'first_name', 'last_name', 'grade', 'total_score', 'percent', 'large_count', 'bonus_score', 'comment'];

export function groupTasks(tasks: readonly TaskMeta[]): Map<string, TaskMeta[]> {
  const groups = new Map<string, TaskMeta[]>();
  for (const task of tasks) {
    if (!groups.has(task.group)) groups.set(task.group, []);
    groups.get(task.group)!.push(task);
  }
  return groups;
}

export type GradeEditActions = {score: (row: StudentRow, task: TaskMeta) => void; comment: (row: StudentRow) => void; grade: (row: StudentRow) => void};

export function buildColumns(tasks: readonly TaskMeta[], canEdit: boolean, order: TaskOrder, collapsed: ReadonlySet<string>, toggleGroup: (name: string) => void, edit?: GradeEditActions, readOnlyFields: readonly string[] = []): ColumnDef<StudentRow>[] {
  const columns: ColumnDef<StudentRow>[] = [
    {id: 'rownum', header: '#', size: 50, minSize: 40, enableSorting: false,
      cell: ({row, table}) => table.getSortedRowModel().rows.findIndex((item) => item.id === row.id) + 1},
    {id: 'username', accessorFn: (row) => row.username, header: 'Username', size: 120, minSize: 1,
      cell: ({row}) => canEdit && row.original.repo_url
        ? <a href={row.original.repo_url} target="_blank" rel="noopener noreferrer">{row.original.username}</a> : row.original.username},
  ];
  if (canEdit) columns.push(
    {id: 'first_name', accessorFn: (row) => row.first_name ?? '', header: 'First Name', minSize: 1, size: 100},
    {id: 'last_name', accessorFn: (row) => row.last_name ?? '', header: 'Last Name', minSize: 1, size: 100},
  );
  columns.push(
    {id: 'grade', accessorFn: (row) => row.grade, header: 'Grade', minSize: 1, size: 70, sortingFn: 'basic',
      cell: ({row}) => {
        const value = row.original.grade_is_override
          ? <span className="grades-override" title="Grade manually set by administrator">{row.original.grade} *</span> : row.original.grade;
        return canEdit && edit ? <Button view="flat" className="grades-cell-action" aria-label={`Edit grade for ${row.original.username}`} onClick={() => edit.grade(row.original)}>{value}</Button> : value;
      }},
    {id: 'total_score', accessorFn: (row) => row.total_score, header: 'Total Score', minSize: 1, size: 95, sortingFn: 'basic'},
    {id: 'percent', accessorFn: (row) => row.percent, header: 'Percent', minSize: 1, size: 80, sortingFn: 'basic', cell: ({row}) => row.original.percent.toFixed(1)},
    {id: 'large_count', accessorFn: (row) => row.large_count, header: 'LHW', minSize: 1, size: 65, sortingFn: 'basic'},
    {id: 'bonus_score', accessorFn: (row) => row.scores.bonus_score ?? 0, header: 'Bonus', minSize: 1, size: 70, sortingFn: 'basic',
      cell: ({row}) => canEdit && edit && !readOnlyFields.includes('scores.bonus_score')
        ? <Button view="flat" className="grades-cell-action" aria-label={`Edit score bonus_score for ${row.original.username}`} onClick={() => edit.score(row.original, {name: 'bonus_score', group: '', group_start: '', score: 0})}>{row.original.scores.bonus_score ?? 0}</Button>
        : row.original.scores.bonus_score ?? 0},
  );
  if (canEdit) columns.push({id: 'comment', accessorFn: (row) => row.comment ?? '', header: 'Comment', minSize: 1, size: 200, cell: ({row}) => edit
    ? <Button view="flat" className="grades-cell-action" aria-label={`Edit comment for ${row.original.username}`} onClick={() => edit.comment(row.original)}>{row.original.comment || <em>No comment</em>}</Button>
    : row.original.comment || <em>No comment</em>});
  const groups = Array.from(groupTasks(tasks), ([name, items]) => ({name, items, start: items[0].group_start}));
  for (const group of orderGroups(groups, order)) {
    columns.push({
      id: groupColumnId(group.name),
      header: () => <Button view="flat" aria-label={`${collapsed.has(group.name) ? 'Expand' : 'Collapse'} ${group.name}`} onClick={() => toggleGroup(group.name)}>{group.name} {collapsed.has(group.name) ? '▸' : '▾'}</Button>,
      enableSorting: false, enableResizing: false,
      columns: [
        ...group.items.map((task): ColumnDef<StudentRow> => ({id: taskColumnId(task), accessorFn: (row) => Object.hasOwn(row.scores, task.name) ? row.scores[task.name] : 0, header: task.name, size: 100, sortingFn: 'basic',
          cell: ({row}) => {
            const value = Object.hasOwn(row.original.scores, task.name) ? row.original.scores[task.name] : 0;
            return canEdit && edit && !readOnlyFields.includes(`scores.${task.name}`) ? <Button view="flat" className="grades-cell-action" aria-label={`Edit score ${task.name} for ${row.original.username}`} onClick={() => edit.score(row.original, task)}>{value}</Button> : value;
          }})),
        {id: groupTotalColumnId(group.name), accessorFn: (row) => group.items.reduce((sum, task) => sum + (Object.hasOwn(row.scores, task.name) ? row.scores[task.name] : 0), 0), header: 'Total', size: 120, enableSorting: false},
      ],
    });
  }
  return columns;
}
