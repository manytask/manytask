import {useState, type ReactNode} from 'react';
import {Alert, Button, Text} from '@gravity-ui/uikit';

import {ProfileDialog} from '../shared/ProfileDialog';
import {FlashMessages} from './FlashMessages';
import type {SharedUiData} from './contracts';

export function AppShell({shared, children}: {shared: SharedUiData; children: ReactNode}) {
  const [profileOpen, setProfileOpen] = useState(false);
  const course = shared.course;
  const percent = course ? (course.maxStartedScore === 0 ? '0.0' : (course.score / course.maxStartedScore * 100).toFixed(1)) : null;

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="app-brand" href={shared.urls.home}>
          {shared.favicon && <img src={shared.favicon} alt="" width="28" height="28" />}
          <Text variant="header-1">Manytask</Text>
        </a>
        <nav className="app-navigation" aria-label="Main navigation">
          {shared.navigation.map((link) => <a key={`${link.label}:${link.href}`} href={link.href}>{link.label}</a>)}
        </nav>
        {course && <div className="course-meta">
          <details><summary>{course.name}</summary>
            <nav aria-label="Courses">{shared.courses.map((link) => <a key={link.href} href={link.href}>{link.label}</a>)}</nav>
          </details>
          {percent !== null && <span aria-label="Course score">{percent}% · {course.score - course.bonusScore}{course.bonusScore > 0 ? `+${course.bonusScore}` : ''}/{course.maxStartedScore}</span>}
        </div>}
        {shared.username && <div className="app-account">
          <Text>{shared.username}</Text>
          <Button onClick={() => setProfileOpen(true)}>Change user info</Button>
          <a href={shared.urls.logout}>Sign out</a>
        </div>}
      </header>
      <div className="shell-messages">
        <FlashMessages flashes={shared.flashes} />
        {shared.errorMessage && <div role="alert"><Alert theme="danger" title="Error" message={shared.errorMessage} /></div>}
      </div>
      <div className="app-content">{children}</div>
      <footer className="app-footer">{shared.version && <span>Manytask {shared.version}</span>}</footer>
      {shared.username && <ProfileDialog shared={shared} open={profileOpen} onClose={() => setProfileOpen(false)} />}
    </div>
  );
}
