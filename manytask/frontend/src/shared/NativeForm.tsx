import type {ReactNode} from 'react';

export function NativeForm({action, csrfToken, children, onSubmit}: {
  action: string; csrfToken: string; children: ReactNode; onSubmit?: React.FormEventHandler<HTMLFormElement>;
}) {
  return <form action={action} method="post" onSubmit={onSubmit}>
    <input type="hidden" name="csrf_token" value={csrfToken}/>{children}
  </form>;
}
