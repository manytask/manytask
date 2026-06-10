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


## How to schedule deadlines

Some tips on how to schedule deadlines.

### Avoid Scheduling Deadlines on Lecture Days

It's better not to set deadlines on the same day as a lecture. Students will likely be preoccupied with completing tasks and may not have time to attend the lecture. We value students' participation in lectures and encourage their presence.


### Deadline Timing and Late Submissions

Deadlines are typically set to 23:59:00. However, when checking for the deadline, Manytask uses time when CI pipeline started. If a student submits their code too close to the deadline (e.g. at 23:58:59), the submission can be marked as late. This should be communicated to the students, so that they are not waiting for the very last moment to submit their solutions. One can also manually update the student's score in the table or using CLI.

### Use soft deadlines

It is generally better to use soft deadlines. If students are given a chance to get even a fractional score for the task they are more likely to solve the task and submit their solution for checks. Soft deadline is also beneficial for the testing systems since it allows to distribute the load more evenly.

Example:


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