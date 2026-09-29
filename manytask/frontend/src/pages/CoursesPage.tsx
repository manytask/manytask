import {useMemo, useState} from 'react';
import {Button, Select, Table, TextInput} from '@gravity-ui/uikit';

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
  const sorted = useMemo(() => [...filtered].sort((a, b) => a.name.localeCompare(b.name)), [filtered]);

  const courseColumns = [
    {id: 'name', name: 'Name', template: (course: CourseRow) => <a href={course.href}>{course.name}</a>},
    {id: 'namespaceSlug', name: 'Namespace', template: (course: CourseRow) => course.namespaceSlug || '—'},
    {id: 'status', name: 'Status', template: (course: CourseRow) => humanizeStatus(course.status)},
    {id: 'editHref', name: 'Edit', template: (course: CourseRow) => course.editHref ? <a href={course.editHref} aria-label={`Edit ${course.name}`}>Edit</a> : null},
  ];
  const namespaceColumns = [
    {id: 'name', name: 'Name', template: (namespace: AdminNamespace) => <a href={namespace.href}>{namespace.name}</a>},
    {id: 'slug', name: 'Slug'},
    {id: 'description', name: 'Description', template: (namespace: AdminNamespace) => namespace.description || '—'},
    {id: 'coursesCount', name: 'Courses'},
    {id: 'usersCount', name: 'Users'},
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
        <Table aria-label="Courses" data={sorted} columns={courseColumns} />
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
      <div className="table-scroll"><Table aria-label="Admin namespaces" data={data.adminNamespaces} columns={namespaceColumns} /></div>
    </section>}
  </main>;
}
