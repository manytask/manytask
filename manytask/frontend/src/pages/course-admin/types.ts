export type CourseUserCandidate = {username: string; firstName: string; lastName: string};

export type CourseFormData = {
  action: string;
  mode: 'create' | 'edit';
  rms: 'gitlab' | 'sourcecraft';
  labels: Record<string, string>;
  values: Record<string, string>;
  namespaces: Array<{id: number; name: string; path: string}>;
  statuses: Array<{value: string; label: string}>;
  showAllScores: boolean;
  accessUrls: null | {users: string; courseAdmin: string};
  courseUsers?: CourseUserCandidate[];
  namespaceLocked?: boolean;
  namespaceError?: string | null;
  cancelUrl?: string | null;
  allowNoNamespace?: boolean;
};
