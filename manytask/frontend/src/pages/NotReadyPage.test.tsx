import {screen} from '@testing-library/react';
import {describe, expect, it} from 'vitest';

import {App} from '../app/App';
import {makeSharedUi, renderUi} from '../test/render';
import {NotReadyPage} from './NotReadyPage';

describe('NotReadyPage', () => {
  it('shows the course name and allowed actions', () => {
    renderUi(
      <NotReadyPage
        shared={makeSharedUi()}
        data={{
          courseName: 'Имя </script>',
          links: [{label: 'Refresh', href: '/course/'}, {label: 'Back to courses list', href: '/'}],
        }}
      />,
    );

    expect(screen.getByText('Имя </script>')).toBeInTheDocument();
    expect(screen.getByRole('link', {name: 'Refresh'})).toHaveAttribute('href', '/course/');
    expect(screen.getByRole('link', {name: 'Back to courses list'})).toHaveAttribute('href', '/');
  });

  it('displays each queued flash once with its severity', () => {
    renderUi(
      <NotReadyPage
        shared={makeSharedUi({flashes: [{category: 'error', message: 'Please try again'}]})}
        data={{courseName: 'python', links: []}}
      />,
    );

    expect(screen.getAllByText('Please try again')).toHaveLength(1);
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('keeps success, warning, and info flash categories', () => {
    renderUi(
      <NotReadyPage
        shared={makeSharedUi({
          flashes: [
            {category: 'success', message: 'Saved'},
            {category: 'warning', message: 'Almost full'},
            {category: 'info', message: 'Maintenance scheduled'},
          ],
        })}
        data={{courseName: 'python', links: []}}
      />,
    );

    expect(screen.getByText('Success')).toBeInTheDocument();
    expect(screen.getByText('Warning')).toBeInTheDocument();
    expect(screen.getByText('Information')).toBeInTheDocument();
    expect(screen.getAllByRole('status')).toHaveLength(3);
  });

  it('explains an incompatible page schema', () => {
    const script = document.createElement('script');
    script.id = 'manytask-page';
    script.type = 'application/json';
    script.textContent = JSON.stringify({schema_version: 2, page: 'not-ready', shared: makeSharedUi(), data: {}});
    document.body.append(script);

    renderUi(<App />);

    expect(screen.getByText(/incompatible.*version/i)).toBeInTheDocument();
  });
});
