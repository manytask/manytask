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

function compactCountdown(remaining: string) {
  return remaining.replace(/^(?:Deadline expires|Next deadline) in:\s*/i, '').trim();
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function DeadlineSchedule({graph, now}: {graph: DeadlineGraphData; now: string}) {
  const [open, setOpen] = useState(false);
  return <details className={`assignment-schedule ${graph.status}`}
    onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary>
      <strong>Current multiplier: {Math.round(graph.percent * 100)}%</strong>
      {graph.hint && <span>{graph.hint}</span>}
      {graph.status !== 'active' && <span className={`assignment-deadline-status ${graph.status}`}>
        {graph.status === 'expired' ? 'Expired' : 'Urgent'}
      </span>}
    </summary>
    {open && <DeadlineGraph graph={graph} now={now} />}
  </details>;
}

export function AssignmentsPage({shared, data}: PageProps<AssignmentsData>) {
  const [order, toggleOrder] = useTaskOrder(shared.username ?? '', data.courseName);
  const [showPassed, setShowPassed] = useState(false);
  const groups = useMemo(() => orderGroups(data.groups, order), [data.groups, order]);

  return <main className="assignments-page">
    <div className="assignments-heading">
      <h1>Assignments</h1>
      <p>{data.courseName}</p>
    </div>
    {data.sourcecraftInviteUrl && <Alert theme="warning" title="SourceCraft invitation" message={<>
      You need to accept the organization invitation to access your repo. Please check your SourceCraft organizations at{' '}
      <a href={data.sourcecraftInviteUrl} target="_blank" rel="noreferrer">{data.sourcecraftInviteUrl}</a>.
    </>} />}
    <div className="assignments-toolbar">
      <span className="assignments-course-status" data-course-status={shared.course?.status}>
        {shared.course?.status.replaceAll('_', ' ')}
      </span>
      <div className="assignments-actions">
        <TaskOrderButton order={order} onToggle={toggleOrder} />
        <Button type="button" view="normal" size="m" onClick={() => setShowPassed((old) => !old)}>
          {showPassed ? 'Hide past deadlines' : 'Show past deadlines'}
        </Button>
      </div>
    </div>
    {groups.length === 0 ? <p>No assignments yet.</p> : <section aria-label="Assignment groups" className="assignment-groups">
      {groups.map((group) => {
        const completed = group.tasks.filter((task) => task.state === 'solved' || task.state === 'over_solved').length;
        const completion = group.tasks.length === 0 ? 0 : Math.round(completed / group.tasks.length * 100);
        const completionLabel = `${completed} of ${group.tasks.length} tasks completed`;
        const onlyTask = group.tasks.length === 1 ? group.tasks[0] : null;
        const showTotal = !onlyTask || onlyTask.earned !== group.earned || onlyTask.score !== group.maximum;
        const currentDeadline = group.deadlines.find((deadline) => !deadline.passed) ?? null;
        const progressDeadline = currentDeadline ?? (showPassed ? group.deadlines[group.deadlines.length - 1] ?? null : null);
        return <article key={`${group.name}:${group.start}`} className={`assignment-group${group.special ? ' special' : ''}`}>
        <div className="assignment-group-top">
          <div className="assignment-group-summary">
            <div className="assignment-group-title">
              <h2>{group.name}</h2>
              {showTotal && <span className="assignment-group-score"
                title="Group total; maximum excludes bonus task points">Total: {group.earned}/{group.maximum}</span>}
            </div>
            <div className="assignment-completion">
              <span>{completionLabel}</span>
              <div className="assignment-completion-track" role="progressbar" aria-label="Task completion"
                aria-valuetext={completionLabel} aria-valuemin={0} aria-valuemax={100} aria-valuenow={completion}>
                <div style={{width: `${completion}%`}} />
              </div>
            </div>
          </div>
          <div className="assignment-deadlines">
            {group.expired && !showPassed && <div className="assignment-expired" title={group.endTz}>
              Expired: {group.endDate} {group.endTime}
            </div>}
            {group.graph && <DeadlineSchedule graph={group.graph} now={data.now} />}
            {group.deadlines.filter((deadline) => showPassed || !deadline.passed).map((deadline, deadlineIndex) => {
              const progress = clampPercent(deadline.progress);
              const isCurrent = deadline === currentDeadline;
              const showProgress = deadline === progressDeadline;
              const countdown = compactCountdown(deadline.remaining);
              const deadlineLabel = `${Math.round(deadline.percent * 100)}% of points until ${deadline.date} ${deadline.time}` +
                (deadline.passed ? ' · Expired' : countdown ? ` · ${countdown} left` : '');
              return <div key={`${deadline.at}:${deadlineIndex}`}
                className={`assignment-deadline${isCurrent ? ' current' : ''}${showProgress ? ' has-progress' : ''}` +
                  `${deadline.passed ? ' passed' : deadline.urgent ? ' urgent' : ''}`}
                aria-current={isCurrent ? 'step' : undefined}>
                <div className="assignment-deadline-copy">
                  <span title={deadline.tz}>{deadlineLabel}</span>
                  {deadline.urgent && !deadline.passed && <span className="assignment-deadline-status urgent">Urgent</span>}
                </div>
                {showProgress && <div className="assignment-time-progress">
                  <span>Time elapsed</span>
                  <div className="assignment-progress" role="progressbar"
                    aria-label={`Time elapsed until ${deadline.date} ${deadline.time}`}
                    aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
                    <div className={deadline.passed ? 'expired' : deadline.urgent ? 'urgent' : 'active'}
                      style={{width: `${progress}%`}} />
                  </div>
                  <span>{progress}%</span>
                </div>}
              </div>})}
          </div>
        </div>
        <div className="assignment-tasks">
          {group.tasks.map((task, taskIndex) => <a key={`${task.name}:${taskIndex}`} href={task.url}
            className={`assignment-task ${task.state}${task.bonus ? ' bonus' : ''}${task.special ? ' special' : ''}`}>
            <span className="assignment-task-main">
              <span className="assignment-task-name">{task.name}</span>
              <strong>{task.earned}/{task.score}</strong>
            </span>
            {(task.special || task.bonus || task.statistics !== null) && <span className="assignment-task-meta">
              {task.special && <span>Special</span>}
              {task.bonus && <span>Bonus</span>}
              {task.statistics !== null && <span>Submitted by {Math.round(task.statistics * 100)}%</span>}
            </span>}
          </a>)}
        </div>
      </article>})}
    </section>}
  </main>;
}
