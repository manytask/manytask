import {useCallback, useEffect, useRef, useState} from 'react';
import {requestJson} from '../../shared/requestJson';
import type {GradesResponse} from './types';

export function useGrades(url: string): {data: GradesResponse | null; loading: boolean; error: string | null; reload: () => Promise<void>} {
  const [data, setData] = useState<GradesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const active = useRef<AbortController | null>(null);
  const reload = useCallback(async () => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setError(null);
    try {
      const next = await requestJson<GradesResponse>(url, '', {signal: controller.signal});
      // The existing API stores html.escape output. Decode exactly one layer
      // for React text nodes, editor drafts and CSV; never interpret it as HTML.
      const entities: Record<string, string> = {'&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'"};
      const students = next.students.map((row) => ({...row,
        comment: row.comment?.replace(/&(amp|lt|gt|quot|#x27);/g, (entity) => entities[entity]) ?? row.comment,
      }));
      if (!controller.signal.aborted) setData({...next, students});
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : 'Unable to load grades');
        throw cause;
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [url]);
  useEffect(() => {
    setData(null);
    void reload().catch(() => {});
    return () => active.current?.abort();
  }, [reload]);
  return {data, loading, error, reload};
}
