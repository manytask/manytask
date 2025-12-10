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
DATABASE_URL=postgresql://user:password@postgres:5432/manytask

# Application
APP_HOST=app.example.com
DOCS_HOST=docs.example.com
INITIAL_INSTANCE_ADMIN=your_gitlab_username
```


---

## 5. Stop Old Deployment

```bash
cd /srv/manytask/old_deploy
sudo docker compose -f docker-compose.development.yml down
```

---

## 6. Start New Deployment

```bash
cd /srv/manytask/app_deploy_new
sudo docker compose -f docker-compose.development.yml up -d --build
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

Restart the application to apply migrations:

```bash
sudo docker restart test-manytask
```

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
        ├── docker-compose.development.yml
        ├── Dockerfile
        ├── manytask/
        └── ...
```
