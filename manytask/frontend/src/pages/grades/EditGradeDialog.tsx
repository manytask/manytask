import {useEffect, useState, type FormEvent} from 'react';
import {Button, Dialog, TextInput} from '@gravity-ui/uikit';
import {requestJson} from '../../shared/requestJson';
import type {StudentRow} from './types';

type Props = {open: boolean; row: StudentRow; csrfToken: string; url: string; clearUrl: string; onClose: () => void; onSaved: () => Promise<void>};

export function EditGradeDialog({open, row, csrfToken, url, clearUrl, onClose, onSaved}: Props) {
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [written, setWritten] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {if (open) {setDraft(row.grade == null ? '' : String(row.grade)); setConfirmClear(false); setWritten(false); setError(null);}}, [open, row]);
  const mutate = async (endpoint: string, body: object) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    let saved = written;
    try {
      if (!saved) {
        await requestJson(endpoint, csrfToken, {method: 'POST', body: JSON.stringify(body)});
        saved = true;
        setWritten(true);
      }
      await onSaved();
      onClose();
    } catch (cause) {setError(`${saved ? 'Grade saved, but refresh failed' : 'Unable to save grade'}: ${cause instanceof Error ? cause.message : 'Unknown error'}`);}
    finally {setBusy(false);}
  };
  const save = (event: FormEvent) => {
    event.preventDefault();
    const grade = Number(draft);
    if (!written && (draft.trim() === '' || !Number.isInteger(grade))) {setError('Enter a valid integer grade'); return;}
    void mutate(url, {username: row.username, grade});
  };
  return <Dialog open={open} onClose={() => {if (!busy) onClose();}} disableEscapeKeyDown={busy} disableOutsideClick={busy} aria-label={`Edit grade for ${row.username}`}>
    <Dialog.Header caption={`Edit grade for ${row.username}`} />
    <Dialog.Body>
      <p>Current grade: {row.grade ?? '—'} {row.grade_is_override && '(manually set)'}</p>
      <form id="edit-grade-form" onSubmit={save}>
        <label htmlFor="edit-grade-input">Grade</label>
        <TextInput id="edit-grade-input" type="number" value={draft} onUpdate={setDraft} disabled={busy || written} controlProps={{step: '1'}} />
      </form>
      {row.grade_is_override && (confirmClear
        ? <div><p>Clear manual grade override? The grade will be automatically recalculated.</p><Button view="outlined-danger" disabled={busy || written} onClick={() => void mutate(clearUrl, {username: row.username})}>Confirm clear override</Button><Button disabled={busy || written} onClick={() => setConfirmClear(false)}>Keep override</Button></div>
        : <Button disabled={busy || written} onClick={() => setConfirmClear(true)}>Clear override</Button>)}
      {error && <p role="alert">{error}</p>}
    </Dialog.Body>
    <Dialog.Footer renderButtons={() => <><Button onClick={onClose} disabled={busy}>Cancel</Button><Button type="submit" form="edit-grade-form" view="action" disabled={busy} loading={busy}>{written ? 'Retry refresh' : 'Save'}</Button></>} />
  </Dialog>;
}
