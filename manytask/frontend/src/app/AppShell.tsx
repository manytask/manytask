import {useEffect, useRef, useState, type ReactNode} from 'react';
import {ArrowRightFromSquare, Bars, ChartColumn, ChevronLeft, ChevronRight, Gear, House, ListCheck, Moon, Person, Xmark} from '@gravity-ui/icons';
import {Alert, Button, Icon, Label, Text} from '@gravity-ui/uikit';

import {ProfileDialog} from '../shared/ProfileDialog';
import {FlashMessages} from './FlashMessages';
import {ThemeControls} from './Theme';
import type {PageName, SharedUiData} from './contracts';

const SIDEBAR_STORAGE_KEY = 'manytask.sidebarCollapsed';
const MOBILE_QUERY = '(max-width: 899px)';

const PAGE_LABELS: Record<PageName, string> = {
  'not-ready': 'Course not ready',
  signup: 'Sign up',
  'signup-yandex-id': 'Sign in',
  'signup-finish': 'Finish registration',
  'create-project': 'Join course',
  courses: 'Courses',
  assignments: 'Assignments',
  grades: 'All Scores',
  'create-course': 'Create course',
  'edit-course': 'Edit Course',
  'instance-admin': 'Instance Admin panel',
  namespaces: 'Namespaces',
  namespace: 'Namespace',
};

const ACTIVE_NAV_LABELS: Partial<Record<PageName, string>> = {
  courses: 'Courses',
  assignments: 'Assignments',
  grades: 'All Scores',
  'edit-course': 'Edit Course',
  'instance-admin': 'Instance Admin panel',
};

function savedCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function mobileViewport(): boolean {
  try {
    return window.matchMedia?.(MOBILE_QUERY).matches ?? false;
  } catch {
    return false;
  }
}

function NavigationIcon({label}: {label: string}) {
  const normalized = label.toLowerCase();
  const data = normalized === 'courses' ? House
    : normalized === 'assignments' ? ListCheck
      : normalized.includes('score') ? ChartColumn
        : normalized.includes('edit') || normalized.includes('admin') || normalized.includes('namespace') ? Gear
          : ArrowRightFromSquare;
  return <Icon data={data} size={18} />;
}

export function AppShell({shared, page, children}: {shared: SharedUiData; page?: PageName; children: ReactNode}) {
  const [profileOpen, setProfileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(savedCollapsed);
  const [isMobile, setIsMobile] = useState(mobileViewport);
  const [mobileOpen, setMobileOpen] = useState(false);
  const openerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const profileOpenerRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const course = shared.course;
  const pageLabel = page ? PAGE_LABELS[page] ?? 'Workspace' : 'Workspace';
  const activeLabel = page ? ACTIVE_NAV_LABELS[page] : undefined;
  const percent = course ? (course.maxStartedScore === 0 ? '0.0' : (course.score / course.maxStartedScore * 100).toFixed(1)) : null;

  useEffect(() => {
    if (!window.matchMedia) return;
    const media = window.matchMedia(MOBILE_QUERY);
    const onChange = (event: MediaQueryListEvent) => {
      setIsMobile(event.matches);
      if (!event.matches) setMobileOpen(false);
    };
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  function closeMobileNavigation() {
    setMobileOpen(false);
    openerRef.current?.focus();
  }

  function closeProfile() {
    setProfileOpen(false);
    if (isMobile) profileOpenerRef.current?.focus();
  }

  useEffect(() => {
    if (!mobileOpen) return;
    closeRef.current?.focus();
  }, [mobileOpen]);

  useEffect(() => {
    if (!mobileOpen || profileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeMobileNavigation();
        return;
      }
      if (event.key !== 'Tab' || !sidebarRef.current) return;
      const focusable = Array.from(sidebarRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
      )).filter((element) => !element.closest('details:not([open])') || element.matches('summary'));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [mobileOpen, profileOpen]);

  useEffect(() => {
    if (!mobileOpen || !profileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      closeProfile();
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [mobileOpen, profileOpen]);

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
    } catch {
      // The layout remains usable for this page when persistent storage is restricted.
    }
  }

  const sidebar = (!isMobile || mobileOpen) && <aside
    ref={sidebarRef}
    className={`app-sidebar${collapsed && !isMobile ? ' app-sidebar_collapsed' : ''}${isMobile ? ' app-sidebar_mobile' : ''}`}
    role={isMobile ? 'dialog' : undefined}
    aria-modal={isMobile ? true : undefined}
    aria-label={isMobile ? 'Navigation' : 'Application sidebar'}
  >
    <div className="app-sidebar__header">
      <a className="app-brand" href={shared.urls.home} aria-label="Manytask">
        {shared.favicon
          ? <img className="app-brand__mark" src={shared.favicon} alt="" width="28" height="28" />
          : <span className="app-brand__mark app-brand__mark_default" aria-hidden="true">M</span>}
        <Text className="sidebar-label" variant="header-1">Manytask</Text>
      </a>
      {isMobile && <Button ref={closeRef} className="app-sidebar__close" view="flat" size="l" aria-label="Close navigation" onClick={closeMobileNavigation}>
        <Icon data={Xmark} size={20} />
      </Button>}
    </div>

    {(course || shared.courses.length > 0) && <details className="course-switcher">
      <summary aria-label="Switch course">
        <span className="course-switcher__mark" aria-hidden="true">{course?.name.slice(0, 1).toUpperCase() ?? 'C'}</span>
        <span className="course-switcher__name sidebar-label">{course?.name ?? 'Select course'}</span>
      </summary>
      <nav aria-label="Courses">
        {shared.courses.map((link) => <a key={link.href} href={link.href}>{link.label}</a>)}
      </nav>
    </details>}

    {shared.capabilities.courseAdmin && <div className="sidebar-admin-label sidebar-label"><Label theme="warning">ADMIN</Label></div>}

    <nav className="app-navigation" aria-label="Main navigation">
      {shared.navigation.map((link) => {
        const active = activeLabel === link.label;
        return <a key={`${link.label}:${link.href}`} href={link.href} aria-label={link.label} aria-current={active ? 'page' : undefined} title={collapsed ? link.label : undefined}>
          <NavigationIcon label={link.label} />
          <span className="sidebar-label">{link.label}</span>
        </a>;
      })}
    </nav>

    <div className="app-sidebar__footer">
      {course && percent !== null && <div className="course-score" aria-label="Course score" title={`${percent}%`}>
        <Icon data={ChartColumn} size={18} />
        <span className="sidebar-label"><strong>{percent}%</strong><small> · {course.score - course.bonusScore}{course.bonusScore > 0 ? `+${course.bonusScore}` : ''}/{course.maxStartedScore}</small></span>
      </div>}
      <details className="appearance-menu">
        <summary aria-label="Appearance"><Icon data={Moon} size={18} /><span className="sidebar-label">Appearance</span></summary>
        <div className="appearance-menu__panel"><ThemeControls /></div>
      </details>
      {shared.username && <div className="app-account">
        <Button ref={profileOpenerRef} view="flat" width="max" aria-label="Change user info" onClick={() => setProfileOpen(true)}>
          <Icon data={Person} size={18} /><span className="sidebar-label app-account__name">{shared.username}</span>
        </Button>
        <a className="app-signout" href={shared.urls.logout} aria-label="Sign out" title="Sign out"><Icon data={ArrowRightFromSquare} size={18} /><span className="sidebar-label">Sign out</span></a>
      </div>}
      {!isMobile && <Button className="sidebar-collapse" view="flat" width="max" aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} onClick={toggleCollapsed}>
        <Icon data={collapsed ? ChevronRight : ChevronLeft} size={18} />
        <span className="sidebar-label">Collapse</span>
      </Button>}
      {shared.version && <small className="app-version sidebar-label">Manytask {shared.version}</small>}
    </div>
  </aside>;

  return (
    <div className={`app-shell${collapsed ? ' app-shell_sidebar-collapsed' : ''}`}>
      {isMobile && mobileOpen && <button className="app-sidebar-overlay" type="button" aria-label="Dismiss navigation" onClick={closeMobileNavigation} />}
      {sidebar}
      <div className="app-workspace">
        <header className="app-topbar">
          <Button ref={openerRef} className="app-mobile-menu" view="flat" size="l" aria-label="Open navigation" onClick={() => setMobileOpen(true)}>
            <Icon data={Bars} size={20} />
          </Button>
          <nav className="app-breadcrumbs" aria-label="Breadcrumb">
            <a href={shared.urls.home}>Manytask</a>
            {course && <><span aria-hidden="true">/</span><a href={shared.navigation.find((link) => link.label === 'Assignments')?.href ?? shared.urls.home}>{course.name}</a></>}
            <span aria-hidden="true">/</span><span aria-current="page">{pageLabel}</span>
          </nav>
        </header>
        <div className="shell-messages">
          <FlashMessages flashes={shared.flashes} />
          {shared.errorMessage && <div role="alert"><Alert theme="danger" title="Error" message={shared.errorMessage} /></div>}
        </div>
        <div className="app-content">{children}</div>
      </div>
      {shared.username && <ProfileDialog shared={shared} open={profileOpen} onClose={closeProfile} />}
    </div>
  );
}
