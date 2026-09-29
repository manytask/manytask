import {useEffect, useState, type FormEvent} from 'react';
import {Button, Dialog, TextInput} from '@gravity-ui/uikit';
import {requestJson} from '../../shared/requestJson';
import type {StudentRow, TaskMeta} from './types';

type Props = {open: boolean; row: StudentRow; task: TaskMeta; csrfToken: string; url: string; onClose: () => void; onSaved: () => Promise<void>};

export function EditScoreDialog({open, row, task, csrfToken, url, onClose, onSaved}: Props) {
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [written, setWritten] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (open) {setDraft(String(Object.hasOwn(row.scores, task.name) ? row.scores[task.name] : 0)); setWritten(false); setError(null);}
  }, [open, row, task]);
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    const score = Number(draft);
    if (draft.trim() === '' || !Number.isFinite(score)) {setError('Enter a valid number'); return;}
    setBusy(true);
    setError(null);
    let saved = written;
    try {
      if (!saved) {
        await requestJson(url, csrfToken, {method: 'POST', body: JSON.stringify({row_data: row, new_scores: {[task.name]: score}})});
        saved = true;
        setWritten(true);
      }
      await onSaved();
      onClose();
    } catch (cause) {setError(`${saved ? 'Score saved, but refresh failed' : 'Unable to save score'}: ${cause instanceof Error ? cause.message : 'Unknown error'}`);}
    finally {setBusy(false);}
  };
  return <Dialog open={open} onClose={() => {if (!busy) onClose();}} disableEscapeKeyDown={busy} disableOutsideClick={busy} aria-label={`Edit score ${task.name} for ${row.username}`}>
    <Dialog.Header caption={`Edit score for ${task.name}`} />
    <Dialog.Body><form id="edit-score-form" onSubmit={(event) => void save(event)}>
      <label htmlFor="edit-score-input">Score</label>
      <TextInput id="edit-score-input" type="number" value={draft} onUpdate={setDraft} disabled={busy || written} controlProps={{step: 'any'}} />
      {error && <p role="alert">{error}</p>}
    </form></Dialog.Body>
    <Dialog.Footer renderButtons={() => <><Button onClick={onClose} disabled={busy}>Cancel</Button><Button type="submit" form="edit-score-form" view="action" disabled={busy} loading={busy}>{written ? 'Retry refresh' : 'Save'}</Button></>} />
  </Dialog>;
}
