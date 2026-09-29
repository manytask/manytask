import {useMemo, useState} from 'react';
import {Alert, Button} from '@gravity-ui/uikit';

import type {PageProps} from '../app/contracts';
import {TaskOrderButton} from '../shared/TaskOrderButton';
import {orderGroups, useTaskOrder} from '../shared/taskOrder';
import {DeadlineGraph, type DeadlineGraphData} from './DeadlineGraph';
import './assignments.css';

export type AssignmentTask = {
  name: string; url: string; score: number; earned: number; bonus: boolean; special: boolean;
  state: 'solved' | 'over_solved' | 'partial' | 'unsolved'; statistics: number | null;
};
export type AssignmentDeadline = {
  at: string; percent: number; passed: boolean; urgent: boolean; remaining: string; progress: number;
  date: string; time: string; tz: string;
};
export type AssignmentGroup = {
  name: string; start: string; end: string; special: boolean; earned: number; maximum: number;
  expired: boolean; endDate: string; endTime: string; endTz: string;
  tasks: AssignmentTask[]; deadlines: AssignmentDeadline[]; graph: DeadlineGraphData | null;
};
export type AssignmentsData = {
  courseName: string; now: string; sourcecraftInviteUrl: string | null; groups: AssignmentGroup[];
};

export function AssignmentsPage({shared, data}: PageProps<AssignmentsData>) {
  const [order, toggleOrder] = useTaskOrder(shared.username ?? '', data.courseName);
  const [showPassed, setShowPassed] = useState(false);
  const groups = useMemo(() => orderGroups(data.groups, order), [data.groups, order]);

  return <main className="assignments-page">
    {data.sourcecraftInviteUrl && <Alert theme="warning" title="SourceCraft invitation" message={<>
      You need to accept the organization invitation to access your repo. Please check your SourceCraft organizations at{' '}
      <a href={data.sourcecraftInviteUrl} target="_blank" rel="noreferrer">{data.sourcecraftInviteUrl}</a>.
    </>} />}
    <div className="assignments-toolbar">
      <span className="assignments-course-status">{shared.course?.status.replaceAll('_', ' ')}</span>
      <div className="assignments-actions">
        <TaskOrderButton order={order} onToggle={toggleOrder} />
        <Button type="button" view="normal" size="m" onClick={() => setShowPassed((old) => !old)}>
          {showPassed ? 'Hide past deadlines' : 'Show past deadlines'}
        </Button>
      </div>
    </div>
    {groups.length === 0 ? <p>No assignments yet.</p> : <section aria-label="Assignment groups" className="assignment-groups">
      {groups.map((group) => <article key={`${group.name}:${group.start}`} className={`assignment-group${group.special ? ' special' : ''}`}>
        <div className="assignment-group-top">
          <div>
            <h2>{group.name}</h2>
            <p className="assignment-group-score">Score: {group.earned}/{group.maximum}</p>
          </div>
          <div className="assignment-deadlines">
            {group.expired && !showPassed && <div className="assignment-expired" title={group.endTz}>
              Expired: {group.endDate} {group.endTime}
            </div>}
            {group.graph && <DeadlineGraph graph={group.graph} now={data.now} />}
            {group.deadlines.filter((deadline) => showPassed || !deadline.passed).map((deadline, deadlineIndex) =>
              <div key={`${deadline.at}:${deadlineIndex}`} className={`assignment-deadline${deadline.passed ? ' passed' : ''}`}>
                <div className="assignment-deadline-head">
                  <strong>{Math.round(deadline.percent * 100)}%</strong>
                  <span className={`assignment-deadline-status ${deadline.passed ? 'expired' : deadline.urgent ? 'urgent' : 'active'}`}>
                    {deadline.passed ? 'Expired' : deadline.urgent ? 'Urgent' : 'Active'}
                  </span>
                </div>
                <div className="assignment-progress"><div className={deadline.passed ? 'expired' : deadline.urgent ? 'urgent' : 'active'}
                  style={{width: `${deadline.progress}%`}} /></div>
                <div className="assignment-deadline-time" title={deadline.tz}>
                  <span>{deadline.date}</span><span>{deadline.time}</span>
                </div>
                <div className="assignment-deadline-hint">{deadline.remaining}</div>
              </div>)}
          </div>
        </div>
        <div className="assignment-tasks">
          {group.tasks.map((task, taskIndex) => <a key={`${task.name}:${taskIndex}`} href={task.url}
            className={`assignment-task ${task.state}${task.bonus ? ' bonus' : ''}${task.special ? ' special' : ''}`}>
            <span className="assignment-task-name">{task.name}</span>
            <strong>{task.earned}/{task.score}</strong>
            <span className="assignment-task-meta">
              {task.special && 'special '}{task.bonus && 'bonus '}{task.statistics ?? 0}
            </span>
          </a>)}
        </div>
      </article>)}
    </section>}
  </main>;
}
