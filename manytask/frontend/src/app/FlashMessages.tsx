import {Alert} from '@gravity-ui/uikit';

import type {SharedUiData} from './contracts';

type FlashTheme = 'danger' | 'warning' | 'success' | 'info';

function appearance(category: string): {theme: FlashTheme; title: string} {
  switch (category) {
    case 'success':
      return {theme: 'success', title: 'Success'};
    case 'warning':
      return {theme: 'warning', title: 'Warning'};
    case 'info':
      return {theme: 'info', title: 'Information'};
    default:
      return {theme: 'danger', title: 'Error'};
  }
}

export function FlashMessages({flashes}: Pick<SharedUiData, 'flashes'>) {
  if (flashes.length === 0) return null;

  return (
    <section className="flash-messages" aria-label="Messages">
      {flashes.map(({category, message}, index) => {
        const {theme, title} = appearance(category);
        return (
          <div key={`${index}:${category}:${message}`} role={theme === 'danger' ? 'alert' : 'status'}>
            <Alert theme={theme} title={title} message={message} />
          </div>
        );
      })}
    </section>
  );
}
