import {useState} from 'react';
import {Alert, Button, Dialog, TextArea, TextInput} from '@gravity-ui/uikit';
import {requestJson} from '../../shared/requestJson';

export type CreatedNamespace = {id: number; name: string; slug: string; description: string | null; gitlab_group_id: number | null};
export function NamespaceDialog({url, csrfToken, onClose, onCreated}: {url: string; csrfToken: string; onClose: () => void; onCreated: (namespace: CreatedNamespace) => void}) {
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true); setError('');
    try {
      const result = await requestJson<CreatedNamespace>(url, csrfToken, {method: 'POST', body: JSON.stringify({name, slug, description: description || null})});
      onCreated(result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  };
  return <Dialog open onClose={() => { if (!busy) onClose(); }} returnFocus><Dialog.Header caption="Create namespace" /><Dialog.Body>
    <form onSubmit={(event) => {event.preventDefault(); void submit();}}>
      <div className="form-fields">
        <label htmlFor="namespace-name">Name</label><TextInput id="namespace-name" value={name} onUpdate={setName} controlProps={{required: true}} />
        <label htmlFor="namespace-slug">Slug</label><TextInput id="namespace-slug" value={slug} onUpdate={setSlug} controlProps={{required: true, pattern: '^[a-zA-Z0-9._-]+$'}} />
        <p>Must start/end with alphanumeric, no consecutive special chars.</p>
        <label htmlFor="namespace-description">Description</label><TextArea id="namespace-description" value={description} onUpdate={setDescription} />
      </div>
      {error && <div role="alert"><Alert theme="danger" title={error} /></div>}
      <div className="form-actions"><Button disabled={busy} onClick={onClose}>Cancel</Button><Button type="submit" view="action" loading={busy}>Create</Button></div>
    </form>
  </Dialog.Body></Dialog>;
}
