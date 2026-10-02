# Run the UI review environment

Requirements: Git, Docker with Compose v2, and an available local port `8082`.
Node.js, Python, and PostgreSQL run inside containers. The first build needs
internet access to download images and dependencies.

From the repository root, with the pull request branch checked out:

```sh
docker compose -f compose.review.yml up --build --detach --wait --wait-timeout 180
```

Open <http://127.0.0.1:8082/__preview__/> and select a role. No account setup or
password is needed:

| Entry | Identity | Access |
| --- | --- | --- |
| `student` | `student000` | Student |
| `course_admin` | `student001` | Course administrator |
| `namespace_admin` | `student002` | Namespace administrator |
| `instance_admin` | `student003` | Instance administrator |

The first start applies database migrations and seeds a course with eight task
groups and 230 students, including zero and negative scores. Staff accounts are
hidden from student viewers in the grades table.

- Assignments: <http://127.0.0.1:8082/sandbox/>
- Grades: <http://127.0.0.1:8082/sandbox/database>
- Switch roles: return to <http://127.0.0.1:8082/__preview__/>.

Flask handlers, PostgreSQL, form validation, CSRF, and permission checks are real.
OAuth and GitLab/SourceCraft operations use test adapters. Task links open local
placeholders; repository hosting and external CI pipelines are not part of this
environment. The preview role links bypass OAuth, and the app binds only to
`127.0.0.1`.

The Compose file builds the application's production image, including frontend
assets. It mounts only the test helpers and course template as read-only files.
The review database is separate from the development Compose environment.

## Logs and health

```sh
docker compose -f compose.review.yml logs --tail=100 app db
curl --fail http://127.0.0.1:8082/__preview__/health
```

## Update, stop, or reset

After updating the checked-out branch, rebuild and restart using the same `up`
command. Existing review data is preserved.

To stop and remove the containers while keeping the database:

```sh
docker compose -f compose.review.yml down
```

To delete the review database and seed fresh data on the next start:

```sh
docker compose -f compose.review.yml down --volumes
docker compose -f compose.review.yml up --build --detach --wait --wait-timeout 180
```
