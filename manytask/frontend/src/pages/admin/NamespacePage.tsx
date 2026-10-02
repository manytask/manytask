import {useState} from 'react';
import {Button, Table, TextInput, withTableSorting} from '@gravity-ui/uikit';
import type {PageProps} from '../../app/contracts';
import {matchesSearch} from '../../shared/search';
import {RoleDialog} from './RoleDialog';
import type {NamespaceData, NamespaceUser, UserCandidate} from './types';
import './admin.css';

const UsersTable = withTableSorting<NamespaceUser>(Table);
const CoursesTable = withTableSorting<NamespaceData['courses'][number]>(Table);
export function NamespacePage({shared, data}: PageProps<NamespaceData>) {
  const [users, setUsers] = useState(data.users);
  const [candidates, setCandidates] = useState(data.availableUsers);
  const [query, setQuery] = useState('');
  const [dialog, setDialog] = useState<{member?: NamespaceUser; remove?: boolean} | null>(null);
  const saved = (candidate: UserCandidate, role: string) => {
    if (role === 'student') {
      setUsers((previous) => previous.filter((user) => user.id !== candidate.id));
      setCandidates((previous) => [...previous.filter((user) => user.id !== candidate.id), candidate]);
    } else {
      setUsers((previous) => [...previous.filter((user) => user.id !== candidate.id), {...candidate, rmsId: candidate.rmsId ?? 0, role}]);
      setCandidates((previous) => previous.filter((user) => user.id !== candidate.id));
    }
    setDialog(null);
  };
  return <main className="admin-page"><h1>{data.namespace.name}</h1>
    <p>Slug: {data.namespace.slug} | ID: {data.namespace.id} | GitLab Group ID: {data.namespace.gitlabGroupId ?? '—'}</p>
    {data.namespace.description && <p>{data.namespace.description}</p>}
    <a href={data.namespacesUrl}>Back to list</a>
    <section><h2>Courses management</h2><a href={data.createCourseUrl}>Create course</a></section>
    <section><h2>Namespace users</h2><p>Users: {users.length}</p>
      <div className="admin-controls"><Button onClick={() => setDialog({})}>Add user</Button><TextInput aria-label="Search members" value={query} onUpdate={setQuery} /><Button onClick={() => setQuery('')}>Clear</Button></div>
      <div className="table-scroll"><UsersTable aria-label="Namespace users" data={users.filter((user) => matchesSearch(user.username, query))} getRowId={(row) => String(row.id)} columns={[
        {id: 'id', name: 'User ID', meta: {sort: true}},
        {id: 'username', name: 'Username', meta: {sort: true}},
        {id: 'rmsId', name: 'RMS ID (GitLab)', meta: {sort: (a: NamespaceUser, b: NamespaceUser) => String(a.rmsId).localeCompare(String(b.rmsId), undefined, {numeric: true})}},
        {id: 'role', name: 'Current Role', meta: {sort: true}, template: (row) => data.roles.find((role) => role.value === row.role)?.label ?? row.role},
        {id: 'actions', name: 'Actions', template: (row) => <div className="admin-controls"><Button aria-label={`Change role ${row.username}`} onClick={() => setDialog({member: row})}>Change role</Button><Button aria-label={`Remove ${row.username}`} onClick={() => setDialog({member: row, remove: true})}>Remove</Button></div>},
      ]} /></div>
      {users.length === 0 && <p>No users in this namespace yet.</p>}
    </section>
    <section><h2>Namespace courses</h2><div className="table-scroll"><CoursesTable aria-label="Namespace courses" data={data.courses} getRowId={(row) => String(row.id)} columns={[
      {id: 'id', name: 'ID', meta: {sort: true}},
      {id: 'name', name: 'Course Name', meta: {sort: true}, template: (row) => <a href={row.href}>{row.name}</a>},
      {id: 'status', name: 'Status', meta: {sort: true}},
      {id: 'gitlabGroup', name: 'GitLab Group', meta: {sort: true}},
      {id: 'owners', name: 'Owners', meta: {sort: true}},
      {id: 'editHref', name: 'Actions', template: (row) => <a href={row.editHref} aria-label={`Edit ${row.name}`}>Edit</a>},
    ]} /></div>{data.courses.length === 0 && <p>No courses in this namespace yet.</p>}</section>
    {dialog && <RoleDialog url={data.usersUrl} csrfToken={shared.csrfToken} users={candidates} roles={data.roles} member={dialog.member} remove={dialog.remove} onClose={() => setDialog(null)} onSaved={saved} />}
  </main>;
}
