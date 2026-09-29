import '@testing-library/jest-dom/vitest';
import {cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';

afterEach(() => {
  cleanup();
  document.getElementById('manytask-page')?.remove();
});
