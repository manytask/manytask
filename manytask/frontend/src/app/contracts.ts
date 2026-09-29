export type PageName =
  | 'not-ready'
  | 'signup'
  | 'signup-yandex-id'
  | 'signup-finish'
  | 'create-project'
  | 'courses'
  | 'assignments'
  | 'grades'
  | 'create-course'
  | 'edit-course'
  | 'instance-admin'
  | 'namespaces'
  | 'namespace';

export type NavLink = {label: string; href: string};

export type SharedUiData = {
  csrfToken: string;
  username: string | null;
  firstName: string;
  lastName: string;
  version: string;
  favicon: string;
  rms: 'gitlab' | 'sourcecraft';
  errorMessage: string | null;
  flashes: Array<{category: string; message: string}>;
  navigation: NavLink[];
  courses: NavLink[];
  urls: {home: string; login: string; logout: string; updateProfile: string};
  capabilities: {
    instanceAdmin: boolean;
    namespaceAdmin: boolean;
    courseAdmin: boolean;
    canCreateCourses: boolean;
    canEditCourse: boolean;
  };
  course: null | {
    name: string;
    status: string;
    score: number;
    bonusScore: number;
    maxStartedScore: number;
  };
};

export type PageEnvelope<T> = {
  schema_version: 1;
  page: PageName;
  shared: SharedUiData;
  data: T;
};

export type PageProps<T> = {shared: SharedUiData; data: T};
