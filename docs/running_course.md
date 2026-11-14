# Running the course

## Course Statuses

Each course can have one of **six statuses** that define its current lifecycle stage.

### 1. Created

* Assigned immediately when a course is created.
* At this stage, the course does not contain any tasks.
* Students cannot access the course page.

### 2. Hidden

* Assigned when the configuration of a course in **Created** status is updated for the first time.
* The course already has tasks, but it remains hidden from students.
* Teachers still have full access.

### 3. In Progress

* Assigned to courses that are currently active and running.

### 4. All Tasks Issued

* Assigned when no more tasks will be added to the course.
* The maximum possible grade for the course is finalized and will not change.
* Indicates that the course is nearing completion.

### 5. Doreshka (upsolving)

* Assigned after the logical completion of a course.
* Allows students who did not achieve a satisfactory grade during the main period to earn additional points.
* Only satisfactory grade is allowed

### 6. Finished

* Assigned when the course is fully completed.
* The course no longer appears on the main student page.

### Managing Course Status

Course status can be changed in two ways:

1. Through the **admin panel**.
2. By specifying the desired status (`created` | `hidden` | `in_progress` | `all_tasks_issued` | `doreshka` | `finished`) in the course configuration file under the `status` field and updating it on the server.


## Managing access

On **Edit course**, the **Course Access** table shows course administrators and users with
access inherited from instance or namespace roles. Use **Grant course admin rights** to promote
a user who is already enrolled on the course. Users who have not enrolled are not eligible.
Revoking course admin rights does not remove access granted by another role.

Instance administrators and namespace administrators manage namespace members in the namespace
panel. Add members by their **Manytask username**; they must have logged into Manytask at least
once. Namespace roles apply across the namespace: a program manager role is not a course admin
role. Only an instance administrator or an administrator of that namespace can assign namespace
roles.

## Editing scores and completion

Course administrators can edit a task's score and **Is solved** flag in the score table's edit
dialog. Check the flag before saving: changing the score also updates the checkbox based on
the task's `min_score`, and you can then adjust it explicitly. For large tasks, this saved flag
determines whether the task contributes to `large_count`. See
[task completion](manytask_yml_reference.md#task-completion) for automatic completion rules.

## Deleting courses and namespaces

Use **Delete course** on **Edit course** to remove a course with **no registered users**.
For a namespace, open its panel and use **Delete Namespace**; the namespace must contain
**no courses**. Both dialogs require the exact current name as confirmation.

These actions remove the corresponding Manytask records. Linked RMS repositories and groups
are preserved. A namespace's name and description can also be changed in its panel without
deleting it.

## How to schedule deadlines

Some tips on how to schedule deadlines.

### Avoid Scheduling Deadlines on Lecture Days

It's better not to set deadlines on the same day as a lecture. Students will likely be preoccupied with completing tasks and may not have time to attend the lecture. We value students' participation in lectures and encourage their presence.


### Deadline Timing and Late Submissions

Deadlines are typically set to 23:59:00. However, when checking for the deadline, Manytask uses time when CI pipeline started. If a student submits their code too close to the deadline (e.g. at 23:58:59), the submission can be marked as late. This should be communicated to the students, so that they are not waiting for the very last moment to submit their solutions. One can also manually update the student's score in the table or using CLI.

### Use soft deadlines

It is generally better to use soft deadlines. If students are given a chance to get even a fractional score for the task they are more likely to solve the task and submit their solution for checks. Soft deadline is also beneficial for the testing systems since it allows to distribute the load more evenly.

For example, here we still give 70% of the score after the first deadline, which was on 2024-12-03:

```yaml
  deadlines: hard
  schedule:
    - group: bpftrace
      enabled: true
      start: 2024-11-01 19:00:00
      steps:
        0.7: 2024-12-03 23:59:00
      end: 2025-02-01 23:59:00
```

### Be Mindful of Students’ Exam Schedules

Avoid setting deadlines on dates when students have exams at external institutions. Understanding your students' schedules will help reduce unnecessary conflicts and stress. It is Ok to move the deadline in case such conflict happens.
