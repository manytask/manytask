# How to schedule deadlines

## Avoid Scheduling Deadlines on Lecture Days

It's better not to set deadlines on the same day as a lecture. Students will likely be preoccupied with completing tasks and may not have time to attend the lecture. We value students' participation in lectures and encourage their presence.


## Deadline Timing and Late Submissions

Deadlines are typically set to 23:59:00. However, there's a possibility that a student might submit their code at 23:58:01, which could mistakenly be marked as late. In such cases, you can manually update the score using the CLI.

## Set Both Soft and Hard Deadlines

Always define both soft and hard deadlines. Students generally manage to stay on track until February 1st in the Fall semester and July 1st in the Spring semester. This approach provides students with a chance to achieve a passing score.

Example (specific to manytask, subject to version differences):


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

## Be Mindful of Students’ Exam Schedules
Avoid setting deadlines on dates when students have exams at external institutions.
Understanding your students' schedules will help reduce unnecessary conflicts and stress.