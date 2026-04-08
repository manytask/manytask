# Development guide

## How to get started developing

### 1. Prerequisites and Access

Before starting development, ensure you have the necessary access:

- A computer with **Docker** installed.
- A GitLab server with **Admin access**. If you need access to [https://gitlab.manytask2.org/](https://gitlab.manytask2.org/), you can request these from **[@artemzhmurov](https://t.me/artemzhmurov)**.
**Alternative for Quick Development**: You can use **Mock RMS mode** (see section below) which doesn't require a GitLab server at all.

## Option A: Using Mock RMS (Recommended for Quick Start)

This is the easiest way to get started with development without needing a GitLab server.

### Step 1 - Prepare the .env file

Copy `.env.example` to `.env` and set the following minimal configuration:

```bash
# Flask token
FLASK_SECRET_KEY=FlaskSecretToken

# Use mock RMS (no GitLab needed)
RMS=mock

# Mock mode requires dummy values for these (not actually used)
GITLAB_URL=http://localhost
GITLAB_CLIENT_ID=dummy
GITLAB_CLIENT_SECRET=dummy

# Database configuration
APPLY_MIGRATIONS=true
INITIAL_INSTANCE_ADMIN=admin
POSTGRES_USER=manytaskadmin
POSTGRES_PASSWORD=localdevdbpass
POSTGRES_DB=manytask
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
DATABASE_URL_EXTERNAL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}
```

### Step 2 - Start the Application

```bash
docker-compose -f docker-compose.development.yml up --build -d
```

Or use the shortcut: `make dev`

### Step 3 - Login with Mock Users

When `RMS=mock`, two users are automatically created:

| Username | Password | RMS ID | Description |
|----------|----------|--------|-------------|
| `admin`  | `admin`  | 1      | Admin user with full access |
| `user`   | `user`   | 2      | Regular user for testing |

You can login with either of these credentials at [http://localhost:8081/](http://localhost:8081/).

**Note**: Mock mode simulates GitLab functionality without requiring an actual GitLab server. This is perfect for:
- Quick local development
- Testing features without GitLab setup
- CI/CD testing environments
- Learning how Manytask works

## Option B: Using Real GitLab


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

For the convenience, the code ships with `Makefile` with shortcuts to commands you need to run linter, typechecker, as well as to format and test the code. You can consult the contents of this file for details of see commands to run one stage or the other. To run all the checks, type

```bash
make check
```

Or, if you are using Colima:

```bash
make check-colima
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

