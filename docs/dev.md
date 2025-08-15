# Development guide


## How to get started developing
### 1. Prerequisites and Access

Before starting development, ensure you have the necessary access:

- **Server access** where you can run an instance of Manytask.
- **Admin access** to our GitLab: [https://gitlab.manytask2.org/](https://gitlab.manytask2.org/)  

You can request these from **[@artemzhmurov](https://t.me/artemzhmurov)**.

Additionally, you need to set up the virtual environment as described in [Development setup](./dev_setup.md).



### 2. Project Structure Overview

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



### 3. Deploying the Service on the Server

#### Step 1 — Register the Application in GitLab

1. Go to: [https://gitlab.manytask2.org/admin/applications](https://gitlab.manytask2.org/admin/applications)
2. Create a new application:
   - **Permissions**: grant all scopes.
   - Mark as **Trusted**.
   - **Callback URL**: `https://*.manytask2.org`  
     Replace `*` with your desired name (avoid existing names!).
3. Copy the **Application ID** and **Secret**.



#### Step 2 — Clone the Project on the Server

1. Connect to the server and go to `/srv/`.
2. Create your own directory inside `/srv/`.
3. Clone your Manytask branch into it.
4. Copy `.env.example` to `.env`.
5. Fill in `.env`:

| Variable                 | Description                                                 |
|--------------------------|-------------------------------------------------------------|
| `FLASK_SECRET_KEY`       | Random string                                               |
| `GITLAB_ADMIN_TOKEN`     | From `/srv/app/.env.common`                                 |
| `GITLAB_CLIENT_ID`       | Application ID from Step 1                                  |
| `GITLAB_CLIENT_SECRET`   | Application Secret from Step 1                              |
| `INITIAL_INSTANCE_ADMIN` | Your GitLab username                                        |
| `DATABASE_URL`           | Database connection string (can be taken from `init-db.sh`) |



#### Step 3 — Start the Application

```bash
docker compose up --build -d
```

### 4. Adding a Course
#### Step 1 — Create the Course in the Admin Panel
1. Go to `admin/panel` → create_course.
2. Fill in all fields and remember the course token.
3. Create the course.

#### Step 2 — Create GitLab Groups and Projects
1. In GitLab: [https://gitlab.manytask2.org/groups/new](https://gitlab.manytask2.org/groups/new)
2. Create an empty public group with the course name.
3. Create a private subgroup (for student repositories).
4. Create a public project inside the group — this will be the shared assignment's repository.

#### Step 3 — Link the Course in Manytask
On the server:
```bash
export TESTER_TOKEN=<course_token>
```
```bash
curl -X POST \
  -H "Authorization: Bearer $TESTER_TOKEN" \
  -H "Content-type: application/x-yaml" \
  --data-binary "@.manytask.example.yml" \
  "https://test.manytask2.org/api/<course_name>/update_config"
```
Replace `<course_name>` with your actual course name.
Once done, your first course will be available in Manytask.


## How to deploy manytask locally
Use `WSL 2`, if you are using Windows
1. Install `postgresql`: 
    ```bash
     sudo apt install postgresql postgresql-contrib
     sudo systemctl start postgresql
     sudo systemctl enable postgresql
    ```
   
2. Create `postgres` user and database:
   ```bash
   sudo -u postgres psql
   CREATE USER <username> WITH PASSWORD '<password>' CREATEDB;
   CREATE DATABASE <database name> WITH OWNER <username>;
   \q
    ```
   
3. Now you can connect to the database using `psql`:
   ```bash
   psql postgresql://<username>:<password>@localhost:5432/<database name>
   ```

4. Copy `.env.example` to `.env` in your working folder. In this file:
- Set `FLASK_SECRET_KEY` to a random string
- Set `DATABASE_URL` to `psql` URL above
- Set the username for the first instance admin with 'INITIAL_INSTANCE_ADMIN'

5. Try to start `Manytask`:
   ```bash
   poetry run flask --app "manytask:create_app()" run --host=0.0.0.0 --port=5050 --reload --debug
   ```
   
6. Manytask will be available on [http://127.0.0.1:5050/](http://127.0.0.1:5050/)

## How to run tests
### On Windows:

1. Use `WSL 2` with your favourite distro
2. Download [Docker Desktop](https://www.docker.com/products/docker-desktop/) 
3. On `WSL integration` in settings: Settings -> Resources -> Enable Integration
4. Now, you can run tests from the project root:
   ```bash
   pytest . -vvv
   ```
   
### On Linux:

1. Download docker
2. Now, you can run tests from the project root:
   ```bash
   pytest . -vvv
   ```