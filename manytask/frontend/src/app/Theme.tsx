import {createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode} from 'react';
import {Button, ThemeProvider} from '@gravity-ui/uikit';

export type ThemePreference = 'light' | 'dark' | 'auto';

type ThemeContextValue = {
  preference: ThemePreference;
  choose: (value: ThemePreference) => void;
};

const ThemeContext = createContext<ThemeContextValue>({preference: 'auto', choose: () => undefined});

function savedPreference(): ThemePreference {
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
  const [preference, setPreference] = useState<ThemePreference>(savedPreference);
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

  const choose = useCallback((value: ThemePreference) => {
    setPreference(value);
    try {
      localStorage.setItem('theme', value);
    } catch {
      // Keep the choice for the current page even if storage is unavailable.
    }
  }, []);

  const context = useMemo(() => ({preference, choose}), [preference, choose]);

  return (
    <ThemeProvider theme={active}>
      <ThemeContext.Provider value={context}>{children}</ThemeContext.Provider>
    </ThemeProvider>
  );
}

export function ThemeControls() {
  const {preference, choose} = useContext(ThemeContext);
  return <div className="theme-switcher" role="group" aria-label="Theme">
    {(['light', 'dark', 'auto'] as const).map((value) => (
      <Button key={value} size="s" view={preference === value ? 'action' : 'flat'} selected={preference === value} onClick={() => choose(value)}>
        {value === 'auto' ? 'Auto' : value === 'dark' ? 'Dark' : 'Light'} Theme
      </Button>
    ))}
  </div>;
}
