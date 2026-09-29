import {useCallback, useEffect, useMemo, useState} from 'react';
import {Alert, Button, Table, TextInput, withTableSorting} from '@gravity-ui/uikit';

import {requestJson} from '../../shared/requestJson';
import {matchesSearch} from '../../shared/search';
import type {CourseUserCandidate} from './types';

type AccessUser = {username: string; first_name: string; last_name: string; access_levels: string[]};
type SortState = Array<{column: string; order: 'asc' | 'desc'}>;
const AccessTable = withTableSorting<AccessUser>(Table);
const levels = ['instance_admin', 'namespace_admin', 'program_manager', 'course_admin'];
const labels: Record<string, string> = {
  instance_admin: 'Instance', namespace_admin: 'Namespace', program_manager: 'Program Manager', course_admin: 'Course',
};

function blankLast(a: string, b: string) {
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;
  return a.toLowerCase().localeCompare(b.toLowerCase());
}

export function CourseAccess({urls, csrfToken, candidates = []}: {
  urls: {users: string; courseAdmin: string}; csrfToken: string; candidates?: CourseUserCandidate[];
}) {
  const [users, setUsers] = useState<AccessUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [grantVisible, setGrantVisible] = useState(false);
  const [candidate, setCandidate] = useState('');
  const [sort, setSort] = useState<SortState>([{column: 'username', order: 'asc'}]);
  const reload = useCallback(async () => {
    const result = await requestJson<{users: AccessUser[]}>(urls.users, csrfToken);
    setUsers(result.users ?? []);
    setError(null);
  }, [urls.users, csrfToken]);
  useEffect(() => { void reload().catch((cause: unknown) => setError(String(cause))); }, [reload]);
  const change = async (username: string, isAdmin: boolean) => {
    try {
      await requestJson(urls.courseAdmin, csrfToken, {method: 'POST', body: JSON.stringify({username, is_admin: isAdmin})});
      await reload();
      if (isAdmin) { setCandidate(''); setGrantVisible(false); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
  };
  const filtered = useMemo(() => users.filter((user) => matchesSearch(
    `${user.username} ${user.first_name} ${user.last_name} ${user.first_name}`, query)), [users, query]);
  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    for (const {column, order} of sort) {
      const difference = column === 'access_levels' ?
        Math.min(...a.access_levels.map((level) => levels.indexOf(level)).filter((rank) => rank >= 0), levels.length) -
        Math.min(...b.access_levels.map((level) => levels.indexOf(level)).filter((rank) => rank >= 0), levels.length) :
        column === 'username' ? a.username.toLowerCase().localeCompare(b.username.toLowerCase()) :
          blankLast(a[column as 'first_name' | 'last_name'], b[column as 'first_name' | 'last_name']);
      if (difference !== 0) return order === 'asc' ? difference : -difference;
    }
    return 0;
  }), [filtered, sort]);
  const columns = [
    {id: 'username', name: 'Login', meta: {sort: true}},
    {id: 'first_name', name: 'First Name', meta: {sort: true}},
    {id: 'last_name', name: 'Last Name', meta: {sort: true}},
    {id: 'access_levels', name: 'Access', meta: {sort: true}, template: (row: AccessUser) => <>
      {levels.filter((level) => row.access_levels.includes(level)).map((level) => <span key={level} className="course-admin-badge">
        {labels[level]}{level === 'course_admin' && <Button size="s" view="flat"
          aria-label={`Revoke course admin rights from ${row.username}`} onClick={() => void change(row.username, false)}>×</Button>}
      </span>)}
    </>},
  ];
  const eligible = candidates.filter((user) => !users.some((row) => row.username === user.username && row.access_levels.includes('course_admin')));
  return <section className="course-admin-access" aria-label="Course Access">
    <h2>Course Access</h2>
    <div className="course-admin-access-controls">
      <TextInput aria-label="Search users" value={query} onUpdate={setQuery} placeholder="Search users..." />
      <Button onClick={() => setQuery('')}>Clear</Button>
      <Button onClick={() => setGrantVisible((value) => !value)}>Grant course admin rights</Button>
    </div>
    {error && <div role="alert"><Alert theme="danger" title={error} /></div>}
    {grantVisible && <div className="course-admin-grant">
      <label htmlFor="course-admin-candidate">Select new course admin</label>
      <select id="course-admin-candidate" value={candidate} onChange={(event) => setCandidate(event.target.value)}>
        <option value="">Select a user</option>
        {eligible.map((user) => <option key={user.username} value={user.username}>
          {user.username} ({user.firstName} {user.lastName})</option>)}
      </select>
      <Button disabled={!candidate} onClick={() => void change(candidate, true)}>Grant rights</Button>
    </div>}
    <AccessTable data={sorted} columns={columns} getRowId={(row) => row.username}
      sortState={sort} onSortStateChange={setSort} aria-label="Course access" />
    {sorted.length === 0 && <p>Nobody has admin access to this course yet.</p>}
  </section>;
}
