import type {PageProps} from '../../app/contracts';
import {CourseForm} from './CourseForm';
import type {CourseFormData} from './types';

export function EditCoursePage(props: PageProps<CourseFormData>) {
  return <CourseForm {...props} />;
}
