import {useState, type FormEvent} from 'react';
import {Alert, Button, Text, TextInput} from '@gravity-ui/uikit';

import type {PageProps} from '../app/contracts';
import {NativeForm} from '../shared/NativeForm';

export type AuthData = {
  kind: 'signup' | 'signup-yandex-id' | 'signup-finish' | 'create-project';
  action: string;
  values: Record<string, string>;
  loginUrl: string;
  sourcecraftUrl: string | null;
  invitationRequired: boolean;
  sourcecraftNotRegistered?: boolean;
};

function Field({name, label, type = 'text', value, required = true, minLength, maxLength, pattern}: {
  name: string; label: string; type?: 'text' | 'email' | 'password'; value?: string;
  required?: boolean; minLength?: number; maxLength?: number; pattern?: string;
}) {
  return <div className="auth-field">
    <label htmlFor={`auth-${name}`}>{label}</label>
    <TextInput id={`auth-${name}`} name={name} type={type} defaultValue={value ?? ''}
      controlProps={{required, minLength, maxLength, pattern}} />
  </div>;
}

export function AuthPage({shared, data}: PageProps<AuthData>) {
  const [passwordError, setPasswordError] = useState(false);
  const isSignup = data.kind === 'signup';
  const isFinish = data.kind === 'signup-finish';
  const isProject = data.kind === 'create-project';

  function submit(event: FormEvent<HTMLFormElement>) {
    if (!isSignup) return;
    const form = event.currentTarget;
    const password = (form.elements.namedItem('password') as HTMLInputElement | null)?.value;
    const confirm = (form.elements.namedItem('password2') as HTMLInputElement | null)?.value;
    if (password !== confirm) {
      event.preventDefault();
      setPasswordError(true);
    } else {
      setPasswordError(false);
    }
  }

  if (data.kind === 'signup-yandex-id') {
    return <main className="auth-page"><section className="auth-card">
      <Text variant="header-1">Sign in</Text>
      <Button href={data.loginUrl} view="action" size="l">Login with Yandex ID</Button>
    </section></main>;
  }

  return <main className="auth-page"><section className="auth-card">
    <Text variant="header-1">{isSignup ? 'Sign up' : isFinish ? 'Finish registration' : 'Join course'}</Text>
    {isSignup && <><Button href={data.loginUrl} view="normal">Login</Button><Text>OR</Text></>}
    {data.sourcecraftNotRegistered && data.sourcecraftUrl &&
      <div role="alert"><Alert theme="warning" title="SourceCraft account required"
        message={<span>To use this course, you need a SourceCraft account. <a href={data.sourcecraftUrl} target="_blank" rel="noopener noreferrer">Register on SourceCraft</a> and then try again.</span>} /></div>}
    {passwordError && <div role="alert">Passwords don't match</div>}
    <NativeForm action={data.action} csrfToken={shared.csrfToken} onSubmit={submit}>
      <div className="form-fields">
        {isSignup && <Field name="username" label="Username" value={data.values.username} minLength={1} maxLength={32} pattern="\S*" />}
        {(isSignup || isFinish) && <>
          <Field name="firstname" label="First name" value={data.values.firstname} minLength={2} maxLength={32} pattern="\S*" />
          <Field name="lastname" label="Last name" value={data.values.lastname} minLength={2} maxLength={32} pattern="\S*" />
        </>}
        {isSignup && <>
          <Field name="email" label="Email address" type="email" value={data.values.email} pattern="[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}" />
          <Field name="password" label="Password" type="password" minLength={6} pattern="\S*" />
          <Field name="password2" label="Re-type password" type="password" minLength={6} pattern="\S*" />
        </>}
        {isProject && <Field name="secret" label="Secret Code" />}
      </div>
      <div className="form-actions">
        <Button type="submit" view="action">{isSignup ? 'Sign up' : isFinish ? 'Finish registration' : 'Join course'}</Button>
        {isProject && <Button href={shared.urls.home}>Back to courses</Button>}
      </div>
    </NativeForm>
  </section></main>;
}
