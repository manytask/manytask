import {lazy, Suspense} from 'react';
import type {InstanceAdminData, NamespacesData, NamespaceData} from '../pages/admin/types';
import type {PageEnvelope} from './contracts';
import type {AuthData} from '../pages/AuthPage';
import type {CoursesData} from '../pages/CoursesPage';
import type {AssignmentsData} from '../pages/AssignmentsPage';
import type {CourseFormData} from '../pages/course-admin/types';
import type {GradesData} from '../pages/grades/types';
import {AppShell} from './AppShell';

const InstanceAdminPage = lazy(() => import('../pages/admin/InstanceAdminPage').then((module) => ({default: module.InstanceAdminPage})));
const NamespacesPage = lazy(() => import('../pages/admin/NamespacesPage').then((module) => ({default: module.NamespacesPage})));
const NamespacePage = lazy(() => import('../pages/admin/NamespacePage').then((module) => ({default: module.NamespacePage})));
const NotReadyPage = lazy(() => import('../pages/NotReadyPage').then((module) => ({default: module.NotReadyPage})));
const AuthPage = lazy(() => import('../pages/AuthPage').then((module) => ({default: module.AuthPage})));
const CoursesPage = lazy(() => import('../pages/CoursesPage').then((module) => ({default: module.CoursesPage})));
const AssignmentsPage = lazy(() => import('../pages/AssignmentsPage').then((module) => ({default: module.AssignmentsPage})));
const GradesPage = lazy(() => import('../pages/grades/GradesPage').then((module) => ({default: module.GradesPage})));
const CreateCoursePage = lazy(() => import('../pages/course-admin/CreateCoursePage').then((module) => ({default: module.CreateCoursePage})));
const EditCoursePage = lazy(() => import('../pages/course-admin/EditCoursePage').then((module) => ({default: module.EditCoursePage})));

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
  return <AppShell shared={envelope.shared} page={envelope.page}>
    <Suspense fallback={<main role="status">Loading page…</main>}>{page}</Suspense>
  </AppShell>;
}
