import '@testing-library/jest-dom/vitest';
import {cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';

// jsdom does not expose matchMedia; Gravity Dialog reads it even while closed.
window.matchMedia ??= () => ({matches: false, addEventListener() {}, removeEventListener() {}} as unknown as MediaQueryList);

afterEach(() => {
  cleanup();
  document.getElementById('manytask-page')?.remove();
});
