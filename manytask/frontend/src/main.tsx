import React from 'react';
import {createRoot} from 'react-dom/client';
import '@gravity-ui/uikit/styles/fonts.css';
import '@gravity-ui/uikit/styles/styles.css';

import {App} from './app/App';
import {Theme} from './app/Theme';
import './app/styles.css';

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <React.StrictMode>
      <Theme>
        <App />
      </Theme>
    </React.StrictMode>,
  );
}
