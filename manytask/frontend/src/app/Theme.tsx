import {useEffect, useState, type ReactNode} from 'react';
import {Button, ThemeProvider} from '@gravity-ui/uikit';

type Preference = 'light' | 'dark' | 'auto';

function savedPreference(): Preference {
  try {
    const value = localStorage.getItem('theme');
    if (value === 'light' || value === 'dark' || value === 'auto') return value;
  } catch {
    // Private browsing and restricted storage must not disable the page.
  }
  return 'auto';
}

function systemDark(): boolean {
  try {
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  } catch {
    return false;
  }
}

export function Theme({children}: {children: ReactNode}) {
  const [preference, setPreference] = useState<Preference>(savedPreference);
  const [dark, setDark] = useState(systemDark);
  const active = preference === 'auto' ? (dark ? 'dark' : 'light') : preference;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', active);
  }, [active]);

  useEffect(() => {
    if (preference !== 'auto' || !window.matchMedia) return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    setDark(media.matches);
    const onChange = (event: MediaQueryListEvent) => setDark(event.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [preference]);

  function choose(value: Preference) {
    setPreference(value);
    try {
      localStorage.setItem('theme', value);
    } catch {
      // Keep the choice for the current page even if storage is unavailable.
    }
  }

  return (
    <ThemeProvider theme={active}>
      <div className="theme-switcher" role="group" aria-label="Theme">
        {(['light', 'dark', 'auto'] as const).map((value) => (
          <Button key={value} view={preference === value ? 'action' : 'normal'} aria-pressed={preference === value} onClick={() => choose(value)}>
            {value === 'auto' ? 'Auto' : value === 'dark' ? 'Dark' : 'Light'} Theme
          </Button>
        ))}
      </div>
      {children}
    </ThemeProvider>
  );
}
