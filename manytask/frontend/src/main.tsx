import React from 'react';
import {createRoot} from 'react-dom/client';
import {ThemeProvider} from '@gravity-ui/uikit';
import '@gravity-ui/uikit/styles/fonts.css';
import '@gravity-ui/uikit/styles/styles.css';

import {App} from './app/App';
import './app/styles.css';

const root = document.getElementById('root');
if (root) {
  createRoot(root).render(
    <React.StrictMode>
      <ThemeProvider theme="light">
        <App />
      </ThemeProvider>
    </React.StrictMode>,
  );
}
