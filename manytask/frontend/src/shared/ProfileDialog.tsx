import {Button, Dialog, TextInput} from '@gravity-ui/uikit';

import type {SharedUiData} from '../app/contracts';
import {NativeForm} from './NativeForm';

export function ProfileDialog({shared, open, onClose}: {shared: SharedUiData; open: boolean; onClose: () => void}) {
  return (
    <Dialog open={open} onClose={onClose} returnFocus>
      <Dialog.Header caption="Change user info" />
      <Dialog.Body>
        <NativeForm action={shared.urls.updateProfile} csrfToken={shared.csrfToken}>
          <input type="hidden" name="action" value="change" />
          <input type="hidden" name="username" value={shared.username ?? ''} />
          <div className="form-fields">
            <label htmlFor="profile-first-name">First name</label>
            <TextInput id="profile-first-name" name="first_name" defaultValue={shared.firstName} />
            <label htmlFor="profile-last-name">Last name</label>
            <TextInput id="profile-last-name" name="last_name" defaultValue={shared.lastName} />
          </div>
          <div className="form-actions">
            <Button type="button" onClick={onClose}>Cancel</Button>
            <Button type="submit" view="action">Save</Button>
          </div>
        </NativeForm>
      </Dialog.Body>
    </Dialog>
  );
}
