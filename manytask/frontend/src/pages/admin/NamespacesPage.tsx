import {Table, withTableSorting} from '@gravity-ui/uikit';
import type {PageProps} from '../../app/contracts';
import type {NamespaceSummary, NamespacesData} from './types';
import './admin.css';

const NamespacesTable = withTableSorting<NamespaceSummary>(Table);
export function NamespaceList({namespaces, counts = false}: NamespacesData & {counts?: boolean}) {
  return <div className="table-scroll"><NamespacesTable aria-label="Namespaces" data={namespaces} getRowId={(row) => String(row.id)} columns={[
    {id: 'id', name: 'ID', meta: {sort: true}},
    {id: 'name', name: 'Name', meta: {sort: true}, template: (row) => <a href={row.href}>{row.name}</a>},
    {id: 'slug', name: 'Slug', meta: {sort: true}},
    {id: 'description', name: 'Description', meta: {sort: true}, template: (row) => row.description || '—'},
    {id: 'gitlabGroupId', name: 'GitLab Group ID', meta: {sort: true}, template: (row) => row.gitlabGroupId ?? '—'},
    ...(counts ? [{id: 'coursesCount', name: 'Courses', meta: {sort: true}}] : []),
    {id: 'usersCount', name: 'Users Count', meta: {sort: true}},
  ]} />{namespaces.length === 0 && <p>No namespaces found.</p>}</div>;
}
export function NamespacesPage({shared, data}: PageProps<NamespacesData>) {
  return <main className="admin-page"><h1>Namespaces</h1><a href={shared.urls.home}>Back to main</a>
    <NamespaceList namespaces={data.namespaces} counts />
    {data.namespaces.length === 0 && <p>{shared.capabilities.instanceAdmin ? 'Create a namespace from the Admin Panel.' : "You don't have access to any namespaces yet. Contact your administrator."}</p>}
  </main>;
}
