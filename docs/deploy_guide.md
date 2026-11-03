# Manytask Deployment Guide for Remote Server

## Prerequisites

- SSH access to the server
- Docker and Docker Compose installed on the server
- Configured nginx-proxy with ACME companion (for HTTPS)

---

## 1. Server Preparation

### 1.1 Connect to the Server

```bash
ssh user@your-server-ip
```

---

## 2. Create Deployment Directory

```bash
sudo mkdir -p /srv/manytask/app_deploy_new
sudo chown $USER:$USER /srv/manytask/app_deploy_new
```

---

## 3. Get Project Code

### Variant 1: Clone from GitHub (recommended)

```bash
cd /srv/manytask
git clone https://github.com/manytask/manytask app_deploy_new
```

To update to a specific version or branch:

```bash
cd /srv/manytask/app_deploy_new
git checkout <tag-or-branch>
```

### Variant 2: Copy from Local Machine via rsync

```bash
rsync -avz --progress \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='*.pyc' \
  --exclude='.venv' \
  --exclude='node_modules' \
  "/path/to/local/project/" \
  user@server-ip:/srv/manytask/app_deploy_new/
```

---

## 4. Configuration Setup

### 4.1 Copy .env File

If there is an existing deployment with `.env`:

```bash
sudo cp /srv/manytask/old_deploy/.env /srv/manytask/app_deploy_new/.env
```


### 4.2 Required Variables in .env

```env
# GitLab
GITLAB_URL=https://gitlab.example.com
GITLAB_ADMIN_TOKEN=your_gitlab_admin_token

# Database
DATABASE_URL=postgresql://user:password@pgbouncer:5432/manytask

# Application
APP_HOST=app.example.com
DOCS_HOST=docs.example.com
INITIAL_INSTANCE_ADMIN=your_gitlab_username
```


---

## 5. Stop Old Deployment

```bash
cd /srv/manytask/old_deploy
sudo docker compose -f compose/docker-compose.production.yml down
```

---

## 6. Start New Deployment

```bash
cd /srv/manytask/app_deploy_new
sudo docker compose -f compose/docker-compose.production.yml up -d --build
```

---

## 7. Database Initialization (First Run)

If the database is empty:

```bash
sudo docker exec -it manytask_postgres psql -U postgres
```

```sql
CREATE USER adminmanytask WITH PASSWORD 'adminpass';
CREATE DATABASE manytask;
GRANT ALL PRIVILEGES ON DATABASE manytask TO adminmanytask;
\c manytask
GRANT ALL ON SCHEMA public TO adminmanytask;
\q
```

The application connects to the database through PgBouncer (`pgbouncer` service) in transaction pooling mode, which keeps the number of PostgreSQL connections low regardless of the number of application workers. To inspect the pools, use the admin console:

```bash
sudo docker exec -e PGPASSWORD=$POSTGRES_PASSWORD manytask_pgbouncer psql -h 127.0.0.1 -U $POSTGRES_USER -d pgbouncer -c 'SHOW POOLS;'
```

Restart the application to apply migrations:

```bash
sudo docker restart test-manytask
```

---

## 7.1 GitLab with an External PostgreSQL (Optional)

To keep one shared, backed-up Postgres for both Manytask and GitLab (so that `pg_dumpall` covers both), run GitLab without its bundled database. Create a separate role and database; the extensions must be created by a superuser in advance, since the role is not one:

```sql
CREATE ROLE gitlab WITH LOGIN PASSWORD 'gitlabpass';
CREATE DATABASE gitlab OWNER gitlab;
\c gitlab
GRANT ALL ON SCHEMA public TO gitlab;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS amcheck;
```

`plpgsql` is built in. See the [GitLab requirements](https://docs.gitlab.com/install/requirements/#extensions) for the current list.

Then in `/etc/gitlab/gitlab.rb` (or `GITLAB_OMNIBUS_CONFIG`):

```ruby
postgresql['enable'] = false
gitlab_rails['db_adapter'] = 'postgresql'
gitlab_rails['db_encoding'] = 'unicode'
gitlab_rails['db_host'] = 'postgres'
gitlab_rails['db_port'] = 5432
gitlab_rails['db_database'] = 'gitlab'
gitlab_rails['db_username'] = 'gitlab'
gitlab_rails['db_password'] = 'gitlabpass'
```

The Postgres server must be reachable from the GitLab container (e.g. a shared Docker network). GitLab loads its schema (about 1000 tables) in a single transaction, so raise `max_locks_per_transaction` (e.g. to `256`) on the Postgres server, otherwise the first migration fails with `out of shared memory`. The `gitlab` data volume still holds repositories and configuration, so back it up as well.

---

## 8. Instance Admin Setup

```bash
sudo docker exec -it manytask_postgres psql -U adminmanytask -d manytask
```

```sql
UPDATE users SET is_instance_admin = true, rms_id = <YOUR_GITLAB_ID> WHERE username = 'your_username';
```

---

## 9. Course Configuration


### 9.1 Send Course Configuration

```bash
curl -X POST "https://app.example.com/api/course-name/update_config" \
  -H "Authorization: Bearer YOUR_COURSE_TOKEN" \
  -H "Content-Type: application/x-yaml" \
  --data-binary @/path/to/.manytask.yml
```

---


## Directory Structure on Server

```
/srv/
├── nginx-proxy/
│   └── docker-compose.yml          # nginx-proxy + acme-companion
└── manytask/
    ├── app_deploy/                  # old deployment
    └── app_deploy_new/              # new deployment
        ├── .env
        ├── compose/docker-compose.production.yml
        ├── manytask/Dockerfile
        ├── manytask/
        └── ...
```
