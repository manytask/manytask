import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Alert, Button, Loader, TextInput} from '@gravity-ui/uikit';
import {Table, useTable} from '@gravity-ui/table';
import {getPaginationRowModel, type ColumnPinningState, type ColumnSizingState, type PaginationState, type SortingState, type VisibilityState} from '@gravity-ui/table/tanstack';
import type {PageProps} from '../../app/contracts';
import {matchesSearchVariants, searchTermVariants} from '../../shared/search';
import {useTaskOrder} from '../../shared/taskOrder';
import {TaskOrderButton} from '../../shared/TaskOrderButton';
import {buildColumns, groupTasks, groupTotalColumnId, personalColumns, pinnedColumns, taskColumnId} from './columns';
import {exportGradesCsv} from './csv';
import {EditScoreDialog} from './EditScoreDialog';
import {EditCommentDialog} from './EditCommentDialog';
import {EditGradeDialog} from './EditGradeDialog';
import {useGrades} from './useGrades';
import type {GradesData, StudentRow, TaskMeta} from './types';
import './grades.css';

const emptyStudents: StudentRow[] = [];
const emptyTasks: TaskMeta[] = [];

export function GradesPage({shared, data: page}: PageProps<GradesData>) {
  const {data, loading, error, reload} = useGrades(page.urls.database);
  const [taskOrder, toggleTaskOrder] = useTaskOrder(shared.username ?? '', page.courseName);
  const [sorting, setSorting] = useState<SortingState>([{id: 'total_score', desc: true}]);
  const [pagination, setPagination] = useState<PaginationState>({pageIndex: 0, pageSize: 100});
  const [allRows, setAllRows] = useState(false);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({});
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [columnPinning, setColumnPinning] = useState<ColumnPinningState>({left: pinnedColumns});
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(() => new Set());
  const [filter, setFilter] = useState('');
  const [hideAdmins, setHideAdmins] = useState(false);
  const [editing, setEditing] = useState<{kind: 'score'; row: StudentRow; task: TaskMeta} | {kind: 'comment' | 'grade'; row: StudentRow} | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const tasks = data?.tasks ?? emptyTasks;
  const students = data?.students ?? emptyStudents;
  const toggleGroup = useCallback((name: string) => setCollapsedGroups((previous) => {
    const next = new Set(previous);
    if (next.has(name)) next.delete(name); else next.add(name);
    return next;
  }), []);
  const columns = useMemo(() => buildColumns(tasks, page.canEdit, taskOrder, collapsedGroups, toggleGroup, {
    score: (row, task) => setEditing({kind: 'score', row, task}),
    comment: (row) => setEditing({kind: 'comment', row}),
    grade: (row) => setEditing({kind: 'grade', row}),
  }, page.readOnlyFields), [tasks, page.canEdit, page.readOnlyFields, taskOrder, collapsedGroups, toggleGroup]);
  const visibility = useMemo(() => {
    const next = {...columnVisibility};
    for (const [group, items] of groupTasks(tasks)) {
      for (const task of items) next[taskColumnId(task)] = !collapsedGroups.has(group);
      next[groupTotalColumnId(group)] = collapsedGroups.has(group);
    }
    return next;
  }, [tasks, collapsedGroups, columnVisibility]);
  const filtered = useMemo(() => {
    const variants = searchTermVariants(filter);
    return students.filter((row) => !(hideAdmins && row.is_admin) && (
      matchesSearchVariants(row.username, variants) ||
      matchesSearchVariants(`${row.first_name ?? ''} ${row.last_name ?? ''} ${row.first_name ?? ''}`, variants)
    ));
  }, [students, filter, hideAdmins]);
  // Only clamp an invalid page when the available rows/page size changes. Sorting,
  // group ordering, visibility and score reloads must not reset a valid page.
  const pageSize = allRows ? Math.max(filtered.length, 1) : pagination.pageSize;
  useEffect(() => {
    setPagination((previous) => {
      const pageIndex = Math.min(previous.pageIndex, Math.max(0, Math.ceil(filtered.length / pageSize) - 1));
      return previous.pageIndex === pageIndex ? previous : {...previous, pageIndex};
    });
  }, [filtered.length, pageSize]);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, []);
  const table = useTable({
    data: filtered, columns, getRowId: (row) => JSON.stringify(['student', row.username]),
    enableSorting: true, enableSortingRemoval: false,
    enableColumnPinning: true, enableColumnResizing: true, columnResizeMode: 'onChange',
    defaultColumn: {minSize: 30, maxSize: 300},
    autoResetPageIndex: false, getPaginationRowModel: getPaginationRowModel(),
    state: {sorting, pagination: {...pagination, pageSize}, columnVisibility: visibility, columnSizing, columnPinning},
    onSortingChange: setSorting, onPaginationChange: setPagination,
    onColumnVisibilityChange: setColumnVisibility, onColumnSizingChange: setColumnSizing, onColumnPinningChange: setColumnPinning,
  });
  const download = () => {
    const labels: Record<string, string> = {bonus_score: 'scores.bonus_score'};
    const rowNumbers = new Map(students.map((row, index) => [row, index + 1]));
    const groups = groupTasks(tasks);
    const exportColumns = table.getVisibleLeafColumns().map((column) => {
      const id = column.id;
      const decoded = id.startsWith('[') ? JSON.parse(id) as string[] : null;
      const task = decoded?.[0] === 'task' ? decoded[2] : null;
      const group = decoded?.[0] === 'group-total' ? decoded[1] : null;
      const items = group == null ? [] : groups.get(group) ?? [];
      return {header: task != null ? `scores.${task}` : group != null ? `${group}_collapsed` : labels[id] ?? id,
        value: (row: StudentRow) => {
          if (id === 'rownum') return rowNumbers.get(row);
          if (id === 'bonus_score') return row.scores.bonus_score ?? 0;
          if (task != null) return Object.hasOwn(row.scores, task) ? row.scores[task] : 0;
          if (group != null) return items.reduce((sum, item) => sum + (Object.hasOwn(row.scores, item.name) ? row.scores[item.name] : 0), 0);
          return row[id as keyof StudentRow];
        }};
    });
    const blob = new Blob([exportGradesCsv(students, exportColumns)], {type: 'text/csv;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const name = page.courseName.replace(/[^a-zA-Z0-9]/g, '_');
    link.download = `${name}_database_export_${new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };
  const personalHidden = columnVisibility.first_name === false;
  return <section className="grades-page" aria-label="Course database">
    <div className="grades-toolbar">
      <h1>Course Database</h1>
      <TaskOrderButton order={taskOrder} onToggle={toggleTaskOrder} />
      {page.canEdit && <>
        <Button onClick={() => setHideAdmins((previous) => !previous)}>{hideAdmins ? 'Show admins' : 'Hide admins'}</Button>
        <Button onClick={() => setColumnVisibility((previous) => ({...previous, ...Object.fromEntries(personalColumns.map((id) => [id, personalHidden]))}))}>{personalHidden ? 'Show personal info' : 'Hide personal info'}</Button>
      </>}
      <Button onClick={() => void reload().catch(() => {})} disabled={loading}>Reload grades</Button>
      {data && <Button onClick={download}>Download CSV</Button>}
    </div>
    <div className="grades-search">
      <TextInput controlRef={searchRef} label="Search students" value={filter} onUpdate={setFilter} placeholder="Search..." />
      <Button onClick={() => setFilter('')}>Clear</Button>
    </div>
    {loading && <div role="status" aria-label="Loading grades"><Loader /></div>}
    {error && <div role="alert"><Alert theme="danger" title="Unable to load grades" message={error} /><Button onClick={() => void reload().catch(() => {})}>Retry</Button></div>}
    {data && <>
      <div className="grades-table-scroll">
        <Table table={table} stickyHeader rowClassName={(row) => row?.original.is_admin ? 'grades-admin-row' : ''} />
      </div>
      {filtered.length === 0 && <p>No students found</p>}
      <div className="grades-pagination">
        <span>{filtered.length} students</span>
        <label>Rows per page <select aria-label="Rows per page" value={allRows ? 'all' : pagination.pageSize} onChange={(event) => {
          setAllRows(event.target.value === 'all');
          if (event.target.value !== 'all') table.setPageSize(Number(event.target.value));
        }}>{[25, 50, 100, 200].map((size) => <option key={size} value={size}>{size}</option>)}<option value="all">All</option></select></label>
        <Button disabled={!table.getCanPreviousPage()} onClick={() => table.firstPage()}>First page</Button>
        <Button disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()}>Previous page</Button>
        <span>Page {pagination.pageIndex + 1} of {Math.max(table.getPageCount(), 1)}</span>
        <Button disabled={!table.getCanNextPage()} onClick={() => table.nextPage()}>Next page</Button>
        <Button disabled={!table.getCanNextPage()} onClick={() => table.lastPage()}>Last page</Button>
      </div>
    </>}
    {editing?.kind === 'score' && <EditScoreDialog open row={editing.row} task={editing.task} csrfToken={shared.csrfToken} url={page.urls.updateScore} onClose={() => setEditing(null)} onSaved={reload} />}
    {editing?.kind === 'comment' && <EditCommentDialog open row={editing.row} csrfToken={shared.csrfToken} url={page.urls.updateComment} onClose={() => setEditing(null)} onSaved={reload} />}
    {editing?.kind === 'grade' && <EditGradeDialog open row={editing.row} csrfToken={shared.csrfToken} url={page.urls.overrideGrade} clearUrl={page.urls.clearGradeOverride} onClose={() => setEditing(null)} onSaved={reload} />}
  </section>;
}
