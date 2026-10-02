import {useState} from 'react';
import {Alert, Button, Dialog, TextInput} from '@gravity-ui/uikit';
import {requestJson} from '../../shared/requestJson';
import {matchesSearch} from '../../shared/search';
import {adminRoles, type NamespaceUser, type UserCandidate} from './types';

type Props = {url: string; csrfToken: string; users: UserCandidate[]; roles?: Array<{value: string; label: string}>; member?: NamespaceUser; remove?: boolean; onClose: () => void; onSaved: (user: UserCandidate, role: string) => void};
export function RoleDialog({url, csrfToken, users, roles = adminRoles, member, remove = false, onClose, onSaved}: Props) {
  const [username, setUsername] = useState(member?.username ?? '');
  const [role, setRole] = useState(member?.role ?? '');
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    const candidate = member ?? users.find((user) => user.username === username);
    if (!candidate) return;
    setBusy(true); setError('');
    try {
      if (remove) await requestJson<void>(`${url}/${candidate.id}`, csrfToken, {method: 'DELETE'});
      else await requestJson(member ? `${url}/${member.id}` : url, csrfToken, {
        method: member ? 'PATCH' : 'POST', body: JSON.stringify(member ? {role} : {username, role}),
      });
      onSaved(candidate, remove ? 'student' : role);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  };
  return <Dialog open onClose={() => { if (!busy) onClose(); }} returnFocus><Dialog.Header caption={remove ? `Remove ${username}` : member ? `Change role ${username}` : 'Assign role in namespace'} /><Dialog.Body>
    <form onSubmit={(event) => {event.preventDefault(); void submit();}}>
      {!member && <div className="form-fields">
        <TextInput aria-label="Search users" value={query} onUpdate={setQuery} placeholder="Search usernames..." />
        <label htmlFor="role-user">Select user</label><select id="role-user" required value={username} onChange={(event) => setUsername(event.target.value)}>
          <option value="">Select a user</option>{users.filter((user) => user.username === username || matchesSearch(user.username, query)).map((user) => <option key={user.id} value={user.username}>{user.username}</option>)}
        </select><p>Only users who have logged in to Manytask are listed.</p>
      </div>}
      {!remove && <div className="form-fields"><label htmlFor="namespace-role">Role</label><select id="namespace-role" required value={role} onChange={(event) => setRole(event.target.value)}>
        <option value="">Select role</option>{roles.filter((item) => member || item.value !== 'student').map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select></div>}
      {(remove || role === 'student') && <p>This will remove {username} from the namespace, their admin privileges and access to the GitLab namespace group. Confirm to continue.</p>}
      {error && <div role="alert"><Alert theme="danger" title={error} /></div>}
      <div className="form-actions"><Button onClick={onClose} disabled={busy}>Cancel</Button><Button type="submit" view="action" loading={busy} disabled={!username || (!remove && !role)}>{remove ? 'Remove user' : member ? 'Save role' : 'Assign role'}</Button></div>
    </form>
  </Dialog.Body></Dialog>;
}
