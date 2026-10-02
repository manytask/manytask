import {Button} from '@gravity-ui/uikit';

import type {TaskOrder} from './taskOrder';

export function TaskOrderButton({order, onToggle}: {order: TaskOrder; onToggle: () => void}) {
  return <Button type="button" view="normal" size="m" onClick={onToggle}>
    {order === 'asc' ? 'Show newest first' : 'Show oldest first'}
  </Button>;
}
