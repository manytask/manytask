import {useCallback, useState} from 'react';

export type TaskOrder = 'asc' | 'desc';

export const taskOrderKey = (username: string, courseName: string) =>
  'manytask:task-group-order:' + JSON.stringify([username, courseName]);

export function orderGroups<T extends {start: string}>(groups: readonly T[], order: TaskOrder): T[] {
  return groups.map((group, index) => ({group, index})).sort((a, b) => {
    const delta = Date.parse(a.group.start) - Date.parse(b.group.start);
    return (Number.isFinite(delta) ? delta * (order === 'asc' ? 1 : -1) : 0) || a.index - b.index;
  }).map((item) => item.group);
}

export function useTaskOrder(username: string, courseName: string): readonly [TaskOrder, () => void] {
  const key = taskOrderKey(username, courseName);
  const [order, setOrder] = useState<TaskOrder>(() => {
    try {
      const saved = localStorage.getItem(key);
      return saved === 'asc' || saved === 'desc' ? saved : 'desc';
    } catch {
      return 'desc';
    }
  });
  const toggle = useCallback(() => {
    setOrder((old) => {
      const next = old === 'asc' ? 'desc' : 'asc';
      try { localStorage.setItem(key, next); } catch { /* selection remains for this page */ }
      return next;
    });
  }, [key]);
  return [order, toggle] as const;
}
