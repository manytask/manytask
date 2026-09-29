import {Alert, Button} from '@gravity-ui/uikit';

import type {NavLink, PageProps} from '../app/contracts';

export function NotReadyPage({data}: PageProps<{courseName: string; links: NavLink[]}>) {
  return (
    <main className="not-ready-page">
      <Alert theme="info" title="Course is not ready" message={data.courseName} />
      <p>A teacher needs to configure this course before it is ready.</p>
      <p>You can refresh the page once the course has been configured.</p>
      <nav className="not-ready-actions" aria-label="Course actions">
        {data.links.map((link) => (
          <Button key={link.href} href={link.href}>
            {link.label}
          </Button>
        ))}
      </nav>
    </main>
  );
}
