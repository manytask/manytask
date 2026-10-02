import {useEffect, useState, type FormEvent} from 'react';
import {Button, Dialog, TextArea} from '@gravity-ui/uikit';
import {requestJson} from '../../shared/requestJson';
import type {StudentRow} from './types';

type Props = {open: boolean; row: StudentRow; csrfToken: string; url: string; onClose: () => void; onSaved: () => Promise<void>};

export function EditCommentDialog({open, row, csrfToken, url, onClose, onSaved}: Props) {
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [written, setWritten] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {if (open) {setDraft(row.comment ?? ''); setWritten(false); setError(null);}}, [open, row]);
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    let saved = written;
    try {
      if (!saved) {
        await requestJson(url, csrfToken, {method: 'POST', body: JSON.stringify({username: row.username, comment: draft || null})});
        saved = true;
        setWritten(true);
      }
      await onSaved();
      onClose();
    } catch (cause) {setError(`${saved ? 'Comment saved, but refresh failed' : 'Unable to save comment'}: ${cause instanceof Error ? cause.message : 'Unknown error'}`);}
    finally {setBusy(false);}
  };
  return <Dialog open={open} returnFocus={false} onClose={() => {if (!busy) onClose();}} disableEscapeKeyDown={busy} disableOutsideClick={busy} aria-label={`Edit comment for ${row.username}`}>
    <Dialog.Header caption={`Edit comment for ${row.username}`} />
    <Dialog.Body><form id="edit-comment-form" onSubmit={(event) => void save(event)}>
      <label htmlFor="edit-comment-input">Comment</label>
      <TextArea id="edit-comment-input" rows={3} value={draft} onUpdate={setDraft} disabled={busy || written} />
      {error && <p role="alert">{error}</p>}
    </form></Dialog.Body>
    <Dialog.Footer renderButtons={() => <><Button onClick={onClose} disabled={busy}>Cancel</Button><Button type="submit" form="edit-comment-form" view="action" disabled={busy} loading={busy}>{written ? 'Retry refresh' : 'Save'}</Button></>} />
  </Dialog>;
}
