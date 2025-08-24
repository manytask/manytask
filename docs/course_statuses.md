# Course Statuses

Each course can have one of **six statuses** that define its current lifecycle stage.

## 1. Created

* Assigned immediately when a course is created.
* At this stage, the course does not contain any tasks.
* Students cannot access the course page.

## 2. Hidden

* Assigned when the configuration of a course in **Created** status is updated for the first time.
* The course already has tasks, but it remains hidden from students.
* Teachers still have full access.

## 3. In Progress

* Assigned to courses that are currently active and running.

## 4. All Tasks Issued

* Assigned when no more tasks will be added to the course.
* The maximum possible grade for the course is finalized and will not change.
* Indicates that the course is nearing completion.

## 5. Doreshka

* Assigned after the logical completion of a course.
* Allows students who did not achieve a satisfactory grade during the main period to earn additional points.

## 6. Finished

* Assigned when the course is fully completed.
* The course no longer appears on the main student page.

---

### Managing Course Status

Course status can be changed in two ways:

1. Through the **admin panel**.
2. By specifying the desired status (`created` | `hidden` | `in_progress` | `all_tasks_issued` | `doreshka` | `finished`) in the course configuration file under the `status` field and updating it on the server.
