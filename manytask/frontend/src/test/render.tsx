import type {ReactNode} from 'react';
import {render} from '@testing-library/react';
import {ThemeProvider} from '@gravity-ui/uikit';

import type {SharedUiData} from '../app/contracts';

export function renderUi(node: ReactNode) {
  return render(<ThemeProvider theme="light">{node}</ThemeProvider>);
}

export function makeSharedUi(overrides: Partial<SharedUiData> = {}): SharedUiData {
  return {
    csrfToken: 'test-csrf',
    username: 'guest',
    firstName: '',
    lastName: '',
    version: '',
    favicon: '',
    rms: 'gitlab',
    errorMessage: null,
    flashes: [],
    navigation: [],
    courses: [],
    urls: {home: '/', login: '/login', logout: '/logout', updateProfile: '/update_profile'},
    capabilities: {
      instanceAdmin: false,
      namespaceAdmin: false,
      courseAdmin: false,
      canCreateCourses: false,
      canEditCourse: false,
    },
    course: null,
    ...overrides,
  };
}
