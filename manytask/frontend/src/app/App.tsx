import {InstanceAdminPage} from '../pages/admin/InstanceAdminPage';
import {NamespacesPage} from '../pages/admin/NamespacesPage';
import {NamespacePage} from '../pages/admin/NamespacePage';
import type {InstanceAdminData, NamespacesData, NamespaceData} from '../pages/admin/types';
import type {PageEnvelope} from './contracts';
import {NotReadyPage} from '../pages/NotReadyPage';
import {AuthPage, type AuthData} from '../pages/AuthPage';
import {CoursesPage, type CoursesData} from '../pages/CoursesPage';
import {AssignmentsPage, type AssignmentsData} from '../pages/AssignmentsPage';
import {GradesPage} from '../pages/grades/GradesPage';
import {CreateCoursePage} from '../pages/course-admin/CreateCoursePage';
import {EditCoursePage} from '../pages/course-admin/EditCoursePage';
import type {CourseFormData} from '../pages/course-admin/types';
import type {GradesData} from '../pages/grades/types';
import {AppShell} from './AppShell';

type NotReadyData = {courseName: string; links: Array<{label: string; href: string}>};

function readPage(): PageEnvelope<unknown> | null {
  const text = document.getElementById('manytask-page')?.textContent;
  if (!text) return null;
  try {
    return JSON.parse(text) as PageEnvelope<unknown>;
  } catch {
    return null;
  }
}

export function App() {
  const envelope = readPage();
  if (!envelope || envelope.schema_version !== 1) {
    return <main role="alert">Incompatible page version. Please refresh this page.</main>;
  }
  let page;
  switch (envelope.page) {
    case 'not-ready':
      page = <NotReadyPage shared={envelope.shared} data={envelope.data as NotReadyData} />;
      break;
    case 'signup':
    case 'signup-yandex-id':
    case 'signup-finish':
    case 'create-project':
      page = <AuthPage shared={envelope.shared} data={envelope.data as AuthData} />;
      break;
    case 'courses':
      page = <CoursesPage shared={envelope.shared} data={envelope.data as CoursesData} />;
      break;
    case 'assignments':
      page = <AssignmentsPage shared={envelope.shared} data={envelope.data as AssignmentsData} />;
      break;
    case 'grades':
      page = <GradesPage shared={envelope.shared} data={envelope.data as GradesData} />;
      break;
    case 'create-course':
      page = <CreateCoursePage shared={envelope.shared} data={envelope.data as CourseFormData} />;
      break;
    case 'edit-course':
      page = <EditCoursePage shared={envelope.shared} data={envelope.data as CourseFormData} />;
      break;
    case 'instance-admin':
      page = <InstanceAdminPage shared={envelope.shared} data={envelope.data as InstanceAdminData} />;
      break;
    case 'namespaces':
      page = <NamespacesPage shared={envelope.shared} data={envelope.data as NamespacesData} />;
      break;
    case 'namespace':
      page = <NamespacePage shared={envelope.shared} data={envelope.data as NamespaceData} />;
      break;
    default:
      page = <main role="alert">This page is not supported by this frontend build.</main>;
  }
  return <AppShell shared={envelope.shared}>{page}</AppShell>;
}
