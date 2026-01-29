# Development guide

## How to get started developing

### 1. Prerequisites and Access

Before starting development, ensure you have the necessary access:

- A computer with **Docker** installed.
- A GitLab server with **Admin access**. If you need access to [https://gitlab.manytask2.org/](https://gitlab.manytask2.org/), you can request these from **[@artemzhmurov](https://t.me/artemzhmurov)**.

### 1. Setting up and running the Manytask application

#### Step 1 — Create Personal Access Token in GitLab

1. In gitlab web-interface, click to your user icon, go to Preferences -> Access Tokens.

2. Create admin token, set following scopes: api, read_api, read_user, read_repository, write_repository, read_registry, write_registry, sudo, admin_mode.

3. Copy token to `GITLAB_ADMIN_TOKEN` environment variable:

#### Step 2 - Register the Application in GitLab

1. In GitLab web-interface, go to the Admin Area -> Applications.

2. Create an application:
   - **Permissions**: api, read_user, sudo, openid, profile, email.
   - Mark as **Trusted**.
   - **Callback URL**: `set the redirect url to http://localhost:8081/login_finish`  
3. Copy the **Application ID** and **Secret** to `GITLAB_CLIENT_ID` and `GITLAB_CLIENT_SECRET` in `.env` file respectively.

#### Step 3 - prepare the .env file

Copy `.env.example` to `.env` and follow the instructions in the file to fill it in. You need to set the following environment variables:

| Variable                 | Description                                                 |
|--------------------------|-------------------------------------------------------------|
| `FLASK_SECRET_KEY`       | Random string                                               |
| `GITLAB_ADMIN_TOKEN`     | Personal Access Token from Step 1                           |
| `GITLAB_CLIENT_ID`       | Application ID from Step 2                                  |
| `GITLAB_CLIENT_SECRET`   | Application Secret from Step 2                              |
| `APPLY_MIGRATIONS`       | Update the database structure if needed (True by default)   |
| `INITIAL_INSTANCE_ADMIN` | Your GitLab username                                        |
| `POSTGRES_USER`          | Username to create in Postgres (e.g. manytaskadmin)         |
| `POSTGRES_PASSWORD`      | Password for this user (e.g. localdevdbpass)                |
| `POSTGRES_DB`            | Database name on the Postgres server (e.g. manytask)        |
| `DATABASE_URL`           | Database connection string (default `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}`) |
| `DATABASE_URL_EXTERNAL`  | Database connection string (default `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}`) |
| `DOCS_HOST`              | Host name for docs (not used in development, can be left blank)             |
| `APP_HOST`               | Host name for the Manytask app (not used in development, can be left blank) |

#### Step 4 — Start the Application

To start the app, run:

```bash
docker-compose -f docker-compose.development.yml up --build -d
```

This should expose Manytask app on port 8081 [http://localhost:8081/](http://localhost:8081/) and docs on port 8080 [http://localhost:8080/](http://localhost:8080/).

You can run `make dev` as a shortcut for this command.

### 4. Adding a Course

#### Step 1 — Create the Course in the Admin Panel

1. Go to `admin/panel` → create_course.
2. Fill in all fields and remember (copy) the course token.
3. Create the course.

#### Step 2 — Create GitLab Groups and Projects

1. Go to the Gitlab web-interface.
2. Create an empty public group with the course name.
3. Create a **private** subgroup (for student repositories).
4. Create a **public** or **internal** project inside the group — this will be the shared assignment's repository.

#### Step 3 — Send the course config to Manytask
On the server:
```bash
export TESTER_TOKEN=<course_token>
```
```bash
curl -X POST \
  -H "Authorization: Bearer $TESTER_TOKEN" \
  -H "Content-type: application/x-yaml" \
  --data-binary "@.manytask.example.yml" \
  "http://localhost:8081/api/<course_name>/update_config"
```
Replace `<course_name>` with your actual course name.
Once done, your first course will be available in Manytask.

## Running tests

```bash
pytest . -vvv
```

## Project Structure Overview

Below is a brief description of each main file in the project:

- **`abstract.py`** – Contains abstract implementations of core objects.
- **`api.py`** – API endpoints for our service.
- **`auth.py`** – Logic related to authentication on the website and in GitLab.
- **`course.py`** – Business logic for the `Course` class.
- **`database.py`** – Database interaction implementation.
- **`glab.py`** – Logic for interacting with GitLab.
- **`main.py`** – Application entry point.
- **`models.py`** – Database model definitions.
- **`web.py`** – Endpoint definitions.

