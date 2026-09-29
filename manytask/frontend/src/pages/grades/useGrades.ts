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
      if (!controller.signal.aborted) setData(next);
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
