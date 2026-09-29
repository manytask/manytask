import {useState} from 'react';
import {Alert, Button, Dialog, Table, TextInput, withTableSorting} from '@gravity-ui/uikit';
import type {PageProps} from '../../app/contracts';
import {NativeForm} from '../../shared/NativeForm';
import {ProfileDialog} from '../../shared/ProfileDialog';
import {requestJson} from '../../shared/requestJson';
import {matchesSearch} from '../../shared/search';
import {NamespaceDialog, type CreatedNamespace} from './NamespaceDialog';
import {NamespaceList} from './NamespacesPage';
import {RoleDialog} from './RoleDialog';
import {adminRoles, type AdminUser, type InstanceAdminData} from './types';

const UsersTable = withTableSorting<AdminUser>(Table);
export function InstanceAdminPage({shared, data}: PageProps<InstanceAdminData>) {
  const [namespaces, setNamespaces] = useState(data.namespaces);
  const [createOpen, setCreateOpen] = useState(false);
  const [roleOpen, setRoleOpen] = useState(false);
  const [namespaceId, setNamespaceId] = useState('');
  const [filter, setFilter] = useState('');
  const [query, setQuery] = useState('');
  const [nativeAction, setNativeAction] = useState<'grant' | 'revoke' | null>(null);
  const [targetUsername, setTargetUsername] = useState('');
  const [nativeQuery, setNativeQuery] = useState('');
  const [profile, setProfile] = useState<AdminUser | null>(null);
  const [refreshError, setRefreshError] = useState<{id: number; message: string} | null>(null);
  const refreshCount = async (id: number) => {
    try {
      const response = await requestJson<{users: Array<{user_id: number; role: string}>}>(`${data.namespaceApiUrl}/${id}/users`, shared.csrfToken);
      setNamespaces((previous) => previous.map((namespace) => namespace.id === id ? {...namespace, usersCount: response.users.length} : namespace));
      setRefreshError(null);
    } catch (cause) {setRefreshError({id, message: `Saved. Could not refresh member count: ${cause instanceof Error ? cause.message : String(cause)}`});}
  };
  const created = (namespace: CreatedNamespace) => {
    // Namespace creation always assigns the creator; reconcile with the read API separately.
    setNamespaces((previous) => [...previous, {id: namespace.id, name: namespace.name, slug: namespace.slug, description: namespace.description ?? '', gitlabGroupId: namespace.gitlab_group_id, usersCount: 1,
      href: data.namespacePanelUrlTemplate.replace(/0$/, String(namespace.id))}]);
    setCreateOpen(false);
    void refreshCount(namespace.id);
  };
  const openNative = (action: 'grant' | 'revoke') => {setNativeAction(action); setTargetUsername(''); setNativeQuery('');};
  return <main className="admin-page"><h1>Instance Admin panel</h1><a href={shared.urls.home}>Back to main</a>
    <section><h2>Courses management</h2><a href={data.createCourseUrl}>Create course</a>
      <div className="form-fields"><label htmlFor="admin-namespace-filter">Filter by namespace</label><select id="admin-namespace-filter" value={filter} onChange={(event) => setFilter(event.target.value)}>
        <option value="">All namespaces</option>{namespaces.map((namespace) => <option key={namespace.id} value={namespace.slug}>{namespace.name}</option>)}
      </select></div><h3>Edit course</h3><ul>{data.courses.filter((course) => !filter || course.namespaceSlug === filter).map((course) => <li key={course.href}><a href={course.href}>{course.name}</a></li>)}</ul>
    </section>
    <section><h2>Namespaces management</h2><div className="admin-controls"><Button onClick={() => setCreateOpen(true)}>Create namespace</Button><Button onClick={() => setRoleOpen(true)}>Assign role in namespace</Button></div>
      {refreshError && <div role="alert"><Alert theme="warning" title={refreshError.message} /><Button onClick={() => void refreshCount(refreshError.id)}>Retry count refresh</Button></div>}
      <NamespaceList namespaces={namespaces} />
    </section>
    <section><h2>User management</h2><div className="admin-controls"><Button onClick={() => openNative('grant')}>Grant admin rights</Button><Button onClick={() => openNative('revoke')}>Revoke admin rights</Button>
      <TextInput aria-label="Search users" value={query} onUpdate={setQuery} placeholder="Search users..." /><Button onClick={() => setQuery('')}>Clear</Button></div>
      <div className="table-scroll"><UsersTable aria-label="Users" data={data.users.filter((user) => matchesSearch(`${user.username} ${user.firstName} ${user.lastName}`, query))} getRowId={(row) => String(row.id)} columns={[
        {id: 'id', name: 'ID', meta: {sort: true}}, {id: 'username', name: 'Username', meta: {sort: true}},
        {id: 'firstName', name: 'First Name', meta: {sort: true}}, {id: 'lastName', name: 'Last Name', meta: {sort: true}},
        {id: 'instanceAdmin', name: 'Instance Admin', meta: {sort: true}, template: (row) => row.instanceAdmin ? 'Yes' : 'No'},
        {id: 'actions', name: 'Profile', template: (row) => <Button aria-label={`Edit profile ${row.username}`} onClick={() => setProfile(row)}>Change user info</Button>},
      ]} /></div>
    </section>
    {profile && <ProfileDialog key={profile.id} shared={{...shared, username: profile.username, firstName: profile.firstName, lastName: profile.lastName}} open onClose={() => setProfile(null)} />}
    {createOpen && <NamespaceDialog url={data.namespaceApiUrl} csrfToken={shared.csrfToken} onClose={() => setCreateOpen(false)} onCreated={created} />}
    {nativeAction && <Dialog open onClose={() => setNativeAction(null)} returnFocus><Dialog.Header caption={nativeAction === 'grant' ? 'Grant Instance Admin Rights' : 'Revoke Instance Admin Rights'} /><Dialog.Body>
      <NativeForm action={data.action} csrfToken={shared.csrfToken}><input type="hidden" name="action" value={nativeAction} />
        <div className="form-fields"><TextInput aria-label="Search users" value={nativeQuery} onUpdate={setNativeQuery} /><label htmlFor="instance-role-user">Select user</label>
          <select id="instance-role-user" name="username" value={targetUsername} onChange={(event) => setTargetUsername(event.target.value)} required>
            <option value="">Select a user</option>{data.users.filter((user) => user.instanceAdmin === (nativeAction === 'revoke') && (user.username === targetUsername || matchesSearch(user.username, nativeQuery))).map((user) => <option key={user.id} value={user.username}>{user.username}</option>)}
          </select></div><div className="form-actions"><Button onClick={() => setNativeAction(null)}>Cancel</Button><Button type="submit" view="action" disabled={!targetUsername}>{nativeAction === 'grant' ? 'Grant Rights' : 'Revoke Rights'}</Button></div>
      </NativeForm>
    </Dialog.Body></Dialog>}
    {roleOpen && !namespaceId && <Dialog open onClose={() => setRoleOpen(false)} returnFocus><Dialog.Header caption="Assign role in namespace" /><Dialog.Body>
      <label htmlFor="role-namespace">Namespace</label><select id="role-namespace" value={namespaceId} onChange={(event) => setNamespaceId(event.target.value)}><option value="">Select namespace</option>{namespaces.map((namespace) => <option key={namespace.id} value={namespace.id}>{namespace.name} ({namespace.slug})</option>)}</select>
      <Button onClick={() => setRoleOpen(false)}>Cancel</Button>
    </Dialog.Body></Dialog>}
    {roleOpen && namespaceId && <RoleDialog url={`${data.namespaceApiUrl}/${namespaceId}/users`} csrfToken={shared.csrfToken} users={data.users} roles={adminRoles.map((role) => role.value === 'namespace_admin' ? {...role, label: 'Namespace Admin (Teacher)'} : role)} onClose={() => {setRoleOpen(false); setNamespaceId('');}} onSaved={() => {setRoleOpen(false); setNamespaceId(''); void refreshCount(Number(namespaceId));}} />}
  </main>;
}
