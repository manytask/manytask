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
