import {useMemo, useState} from 'react';
import {Button, Select, Table, TextInput, withTableSorting} from '@gravity-ui/uikit';

import type {PageProps} from '../app/contracts';
import {matchesSearchVariants, searchTermVariants} from '../shared/search';
import './CoursesPage.css';

export type CourseRow = {
  name: string;
  status: string;
  href: string;
  owners: string;
  namespaceSlug: string;
  editHref: string | null;
};

export type AdminNamespace = {
  id: number;
  name: string;
  href: string;
  slug: string;
  description: string;
  coursesCount: number;
  usersCount: number;
};

export type CoursesData = {
  courses: CourseRow[];
  statusOrder: string[];
  adminNamespaces: AdminNamespace[];
  createCourseUrl: string | null;
  instanceAdminUrl: string | null;
  namespacesUrl: string | null;
};

const VIEW_STORAGE_KEY = 'manytask.coursesView';
const humanizeStatus = (status: string) => status.replace(/_/g, ' ');
type SortState = Array<{column: string; order: 'asc' | 'desc'}>;
const SortableCoursesTable = withTableSorting<CourseRow>(Table);
const SortableNamespacesTable = withTableSorting<AdminNamespace>(Table);

function compareText(a: string, b: string): number {
  return a.toLowerCase().localeCompare(b.toLowerCase());
}

function sortCourses(rows: CourseRow[], sort: SortState, statusOrder: string[]): CourseRow[] {
  const rank = (status: string) => {
    const index = statusOrder.indexOf(status);
    return index === -1 ? statusOrder.length : index;
  };
  return [...rows].sort((a, b) => {
    for (const {column, order} of sort) {
      if (column === 'namespaceSlug') {
        if (!a.namespaceSlug || !b.namespaceSlug) {
          if (!a.namespaceSlug && !b.namespaceSlug) continue;
          return !a.namespaceSlug ? 1 : -1;
        }
      }
      const difference = column === 'name' ? compareText(a.name, b.name)
        : column === 'namespaceSlug' ? compareText(a.namespaceSlug, b.namespaceSlug)
        : column === 'status' ? rank(a.status) - rank(b.status) : 0;
      if (difference !== 0) return order === 'asc' ? difference : -difference;
    }
    return 0;
  });
}

function sortNamespaces(rows: AdminNamespace[], sort: SortState): AdminNamespace[] {
  return [...rows].sort((a, b) => {
    for (const {column, order} of sort) {
      const difference = column === 'name' ? compareText(a.name, b.name)
        : column === 'slug' ? compareText(a.slug, b.slug)
        : column === 'description' ? compareText(a.description, b.description)
        : column === 'coursesCount' ? a.coursesCount - b.coursesCount
        : column === 'usersCount' ? a.usersCount - b.usersCount : 0;
      if (difference !== 0) return order === 'asc' ? difference : -difference;
    }
    return 0;
  });
}

function initialView(): 'list' | 'table' {
  try { return localStorage.getItem(VIEW_STORAGE_KEY) === 'table' ? 'table' : 'list'; }
  catch { return 'list'; }
}

export function CoursesPage({data}: PageProps<CoursesData>) {
  const [view, setView] = useState<'list' | 'table'>(initialView);
  const [completedVisible, setCompletedVisible] = useState(false);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [courseInput, setCourseInput] = useState('');
  const [courseSort, setCourseSort] = useState<SortState>([{column: 'name', order: 'asc'}]);
  const [namespaceSort, setNamespaceSort] = useState<SortState>([{column: 'name', order: 'asc'}]);

  const changeView = (next: 'list' | 'table') => {
    setView(next);
    try { localStorage.setItem(VIEW_STORAGE_KEY, next); } catch { /* in-memory choice remains */ }
  };

  const statuses = useMemo(() => {
    const present = [...new Set(data.courses.map((course) => course.status))];
    const rank = (value: string) => {
      const index = data.statusOrder.indexOf(value);
      return index === -1 ? data.statusOrder.length : index;
    };
    return present.sort((a, b) => rank(a) - rank(b));
  }, [data.courses, data.statusOrder]);
  const variants = useMemo(() => searchTermVariants(query), [query]);
  const filtered = useMemo(() => data.courses.filter((course) =>
    (!status || course.status === status) &&
    (matchesSearchVariants(course.name, variants) || matchesSearchVariants(course.namespaceSlug, variants))),
  [data.courses, status, variants]);
  const sorted = useMemo(() => sortCourses(filtered, courseSort, data.statusOrder), [filtered, courseSort, data.statusOrder]);
  const sortedNamespaces = useMemo(() => sortNamespaces(data.adminNamespaces, namespaceSort), [data.adminNamespaces, namespaceSort]);

  const courseColumns = [
    {id: 'name', name: 'Name', meta: {sort: true}, template: (course: CourseRow) => <a href={course.href}>{course.name}</a>},
    {id: 'namespaceSlug', name: 'Namespace', meta: {sort: true}, template: (course: CourseRow) => course.namespaceSlug || '—'},
    {id: 'status', name: 'Status', meta: {sort: true}, template: (course: CourseRow) => humanizeStatus(course.status)},
    {id: 'editHref', name: 'Edit', template: (course: CourseRow) => course.editHref ? <a href={course.editHref} aria-label={`Edit ${course.name}`}>Edit</a> : null},
  ];
  const namespaceColumns = [
    {id: 'name', name: 'Name', meta: {sort: true}, template: (namespace: AdminNamespace) => <a href={namespace.href}>{namespace.name}</a>},
    {id: 'slug', name: 'Slug', meta: {sort: true}},
    {id: 'description', name: 'Description', meta: {sort: true}, template: (namespace: AdminNamespace) => namespace.description || '—'},
    {id: 'coursesCount', name: 'Courses', meta: {sort: true}},
    {id: 'usersCount', name: 'Users', meta: {sort: true}},
    {id: 'href', name: 'Edit', template: (namespace: AdminNamespace) => <a href={namespace.href} aria-label={`Edit ${namespace.name}`}>Edit</a>},
  ];

  return <main className="courses-page">
    <h1>List of courses</h1>
    <Button onClick={() => changeView(view === 'list' ? 'table' : 'list')}>
      {view === 'list' ? 'Table view' : 'List view'}
    </Button>

    {view === 'list' ? <section aria-label="Course list" className="courses-list">
      <Button onClick={() => setCompletedVisible(!completedVisible)}>
        {completedVisible ? 'Hide completed courses' : 'Show completed courses'}
      </Button>
      {completedVisible && <ul>
        {data.courses.filter((course) => course.status === 'finished').map((course) => <li key={course.href}>
          <a href={course.href}>{course.name}</a> <span>{humanizeStatus(course.status)}</span>
        </li>)}
        {!data.courses.some((course) => course.status === 'finished') && <li>No finished courses yet.</li>}
      </ul>}
      <ul>
        {data.courses.filter((course) => course.status !== 'finished').map((course) => <li key={course.href}>
          <a href={course.href}>{course.name}</a> <span>{humanizeStatus(course.status)}</span>
        </li>)}
        {!data.courses.some((course) => course.status !== 'finished') && <li>Unfortunately, there are no courses yet.</li>}
      </ul>
    </section> : <section className="courses-table-section">
      <div className="courses-controls">
        <label htmlFor="courses-search">Search courses</label>
        <TextInput id="courses-search" value={query} onUpdate={setQuery} placeholder="Search courses..." />
        <Select
          aria-label="Course status"
          value={[status]}
          onUpdate={(values) => setStatus(values[0] || '')}
          options={[{value: '', content: 'All statuses'}, ...statuses.map((value) => ({value, content: humanizeStatus(value)}))]}
        />
        <Button onClick={() => { setQuery(''); setStatus(''); }}>Clear</Button>
      </div>
      <div className="table-scroll">
        <SortableCoursesTable aria-label="Courses" data={sorted} columns={courseColumns} sortState={courseSort} onSortStateChange={setCourseSort} />
      </div>
      {sorted.length === 0 && <p>Unfortunately, there are no courses yet.</p>}
    </section>}

    <form className="courses-enroll" action={`/${courseInput.trim()}`} method="get">
      <label htmlFor="course-input">Register on new course</label>
      <TextInput id="course-input" value={courseInput} onUpdate={setCourseInput} placeholder="Course title..." controlProps={{required: true}} />
      <Button type="submit" view="action">Go</Button>
    </form>

    <div className="courses-admin-actions">
      {data.createCourseUrl && <a href={data.createCourseUrl}>Create course</a>}
      {data.namespacesUrl && <a href={data.namespacesUrl}>Namespaces</a>}
      {data.instanceAdminUrl && <a href={data.instanceAdminUrl}>Instance Admin panel</a>}
    </div>
    {data.adminNamespaces.length > 0 && <section className="courses-namespaces">
      <h2>Namespaces you administer</h2>
      <div className="table-scroll"><SortableNamespacesTable aria-label="Admin namespaces" data={sortedNamespaces} columns={namespaceColumns} sortState={namespaceSort} onSortStateChange={setNamespaceSort} /></div>
    </section>}
  </main>;
}
