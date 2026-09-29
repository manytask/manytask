import type {PageEnvelope} from './contracts';
import {NotReadyPage} from '../pages/NotReadyPage';

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
  switch (envelope.page) {
    case 'not-ready':
      return <NotReadyPage shared={envelope.shared} data={envelope.data as NotReadyData} />;
    default:
      return <main role="alert">This page is not supported by this frontend build.</main>;
  }
}
