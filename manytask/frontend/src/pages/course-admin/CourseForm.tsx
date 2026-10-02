import {useRef, useState, type FormEvent} from 'react';
import {Alert, Button, Checkbox, Select, TextInput} from '@gravity-ui/uikit';

import type {PageProps} from '../../app/contracts';
import {NativeForm} from '../../shared/NativeForm';
import {CourseAccess} from './CourseAccess';
import type {CourseFormData} from './types';
import './course-admin.css';

const fallbackLabels: Record<string, string> = {
  section_header: 'GitLab Configuration', course_group_label: 'Course Group',
  course_public_repo_label: 'Public Repo', course_students_group_label: 'Students Group',
  default_branch_label: 'Default Branch',
};

function Field({name, label, value, onUpdate, type = 'text', required = false, disabled = false}: {
  name: string; label: string; value: string; onUpdate?: (value: string) => void;
  type?: 'text' | 'password'; required?: boolean; disabled?: boolean;
}) {
  return <label className="course-admin-field">{label}
    {onUpdate ? <TextInput name={name} type={type} value={value} onUpdate={onUpdate} disabled={disabled}
      controlProps={{required, autoComplete: 'off'}} /> :
      <TextInput name={name} type={type} defaultValue={value} disabled={disabled}
        controlProps={{required, autoComplete: 'off'}} />}
  </label>;
}

function suggestion(group: string, namespacePath: string, namespaceId: string, rms: CourseFormData['rms']) {
  if (!group) return {publicRepo: '', studentsGroup: ''};
  const now = new Date();
  const year = now.getFullYear();
  const semester = now.getMonth() <= 5 ? 'spring' : 'fall';
  if (rms === 'sourcecraft') {
    const suffix = `${String(year).slice(-2)}${semester[0]}`;
    return {publicRepo: `${group}-public-${suffix}`, studentsGroup: `${group}-st-${suffix}`};
  }
  const path = namespaceId !== '0' && namespacePath && !group.includes('/') ? `${namespacePath}/${group}` : group;
  return {publicRepo: `${path}/public-${year}-${semester}`, studentsGroup: `${path}/students-${year}-${semester}`};
}

export function CourseForm({shared, data}: PageProps<CourseFormData>) {
  const edit = data.mode === 'edit';
  const labels = {...fallbackLabels, ...data.labels};
  const initialNamespace = data.values.namespace_id ?? (data.namespaces[0] ? String(data.namespaces[0].id) : '0');
  const [namespaceId, setNamespaceId] = useState(initialNamespace);
  const [group, setGroup] = useState(data.values[edit ? 'gitlab_course_group' : 'course_group'] ?? '');
  const [publicRepo, setPublicRepo] = useState(data.values[edit ? 'gitlab_course_public_repo' : 'course_public_repo'] ?? '');
  const [studentsGroup, setStudentsGroup] = useState(data.values[edit ? 'gitlab_course_students_group' : 'course_students_group'] ?? '');
  const [error, setError] = useState<string | null>(data.namespaceError ?? null);
  const publicTouched = useRef(Boolean(publicRepo));
  const studentsTouched = useRef(Boolean(studentsGroup));
  const pathFor = (id: string) => data.namespaces.find((ns) => String(ns.id) === id)?.path ?? '';
  const updateSuggestions = (nextGroup: string, nextNamespace: string) => {
    if (edit) return;
    const next = suggestion(nextGroup, pathFor(nextNamespace), nextNamespace, data.rms);
    if (!publicTouched.current) setPublicRepo(next.publicRepo);
    if (!studentsTouched.current) setStudentsGroup(next.studentsGroup);
  };
  const validate = (event: FormEvent<HTMLFormElement>) => {
    if (edit) return;
    const namespacePath = pathFor(namespaceId);
    const foreignGroup = data.rms === 'gitlab' && namespaceId !== '0' && group.includes('/') &&
      !group.startsWith(`${namespacePath}/`);
    const prefix = data.rms === 'sourcecraft' ? group :
      (namespaceId === '0' || group.includes('/') ? group : `${namespacePath}/${group}`) + '/';
    if (data.namespaceError || error || !namespaceId || !group || foreignGroup ||
      !publicRepo.startsWith(prefix) || !studentsGroup.startsWith(prefix)) {
      event.preventDefault();
      setError(data.rms === 'sourcecraft' ? 'Repository names must begin with the course prefix' :
        'Repository paths must begin with the namespace and course group');
    }
  };
  const fieldNames = edit ? {
    group: 'gitlab_course_group', publicRepo: 'gitlab_course_public_repo',
    studentsGroup: 'gitlab_course_students_group', branch: 'gitlab_default_branch',
  } : {group: 'course_group', publicRepo: 'course_public_repo',
    studentsGroup: 'course_students_group', branch: 'default_branch'};
  return <main className="course-admin-page">
    <h1>{edit ? `Edit Course: ${data.values.course_name ?? ''}` : 'Create New Course'}</h1>
    {shared.errorMessage && <div role="alert"><Alert theme="danger" title={shared.errorMessage} /></div>}
    {error && <div role="alert"><Alert theme="danger" title={error} /></div>}
    <NativeForm action={data.action} csrfToken={shared.csrfToken} onSubmit={validate}>
      <div className="course-admin-columns">
        <section><h2>Basic Course Information</h2>
          {edit ? <Field name="" label="Unique Course Name" value={data.values.course_name ?? ''} disabled /> :
            <Field name="unique_course_name" label="Unique Course Name" value={data.values.unique_course_name ?? ''} required />}
          {!edit && <label className="course-admin-field">Namespace
            <Select name={data.namespaceLocked ? undefined : 'namespace_id'}
              value={[namespaceId]} onUpdate={(value) => {
                const next = value[0] ?? '';
                setNamespaceId(next); updateSuggestions(group, next); setError(data.namespaceError ?? null);
              }} disabled={data.namespaceLocked || (data.namespaces.length === 0 && namespaceId === '0')}
              options={[...(data.allowNoNamespace !== false ? [{value: '0', content: 'No namespace'}] : []), ...data.namespaces.map((ns) =>
                ({value: String(ns.id), content: ns.name}))]} />
            {(data.namespaceLocked || (data.namespaces.length === 0 && namespaceId === '0')) &&
              <input type="hidden" name="namespace_id" value={namespaceId} />}
          </label>}
          <Field name="registration_secret" label="Registration Secret"
            value={data.values.registration_secret ?? ''} type={edit ? 'password' : 'text'} required />
          <Field name="token" label="Course Token" value={data.values.token ?? ''}
            type={edit ? 'password' : 'text'} required={!edit} disabled={edit} />
          {edit && <fieldset><legend>Course Status</legend>{data.statuses.map((status) =>
            <label key={status.value} className="course-admin-status"><input type="radio" name="course_status"
              value={status.value} defaultChecked={data.values.course_status === status.value} />{status.label}</label>)}</fieldset>}
          <Checkbox name="show_allscores" value="on" defaultChecked={data.showAllScores}>Show All Scores</Checkbox>
        </section>
        <section><h2>{edit ? (data.rms === 'sourcecraft' ? 'SourceCraft Configuration' : 'GitLab Configuration') : labels.section_header}</h2>
          {edit && data.rms === 'sourcecraft' ?
            <input type="hidden" name="gitlab_course_group" value={group || 'unused-non-gitlab'} /> :
            <Field name={fieldNames.group} label={labels.course_group_label} value={group} required
              onUpdate={(value) => { setGroup(value); updateSuggestions(value, namespaceId); setError(null); }} />}
          <Field name={fieldNames.publicRepo} label={labels.course_public_repo_label}
            value={publicRepo} required onUpdate={(value) => { publicTouched.current = true; setPublicRepo(value); setError(null); }} />
          <Field name={fieldNames.studentsGroup} label={labels.course_students_group_label}
            value={studentsGroup} required={!edit} onUpdate={(value) => { studentsTouched.current = true; setStudentsGroup(value); setError(null); }} />
          <Field name={fieldNames.branch} label={labels.default_branch_label}
            value={data.values[fieldNames.branch] ?? 'main'} required />
        </section>
      </div>
      <div className="course-admin-actions"><Button type="submit" view="action">{edit ? 'Save changes' : 'Create course'}</Button>
        {edit && data.cancelUrl && <Button href={data.cancelUrl}>Cancel</Button>}</div>
    </NativeForm>
    {edit && data.accessUrls && <CourseAccess urls={data.accessUrls} csrfToken={shared.csrfToken}
      candidates={data.courseUsers ?? []} />}
  </main>;
}
