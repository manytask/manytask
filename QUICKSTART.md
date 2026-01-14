# 🚀 Manytask Local Development - Quick Start

> **New to Manytask?** Follow these 9 simple steps to get started!

## Prerequisites
- ✅ Docker & Docker Compose installed
- ✅ Access to [gitlab.manytask2.org](https://gitlab.manytask2.org) (contact [@artemzhmurov](https://t.me/artemzhmurov))

---

## Step-by-Step Guide

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/manytask/manytask.git
cd manytask
```

### 2️⃣ Create GitLab OAuth Application
Go to: [gitlab.manytask2.org/admin/applications](https://gitlab.manytask2.org/admin/applications)

**Settings:**
- Redirect URI: `http://localhost:8081/login_finish`
- Trusted: ✅ Yes
- Confidential: ✅ Yes
- Scopes: ✅ Select all

**Save and copy:** Application ID & Secret

### 3️⃣ Configure Environment
```bash
cp .env.example .env
```

Edit `.env` and fill:
```env
FLASK_SECRET_KEY=random-string-here
GITLAB_ADMIN_TOKEN=your-gitlab-token
GITLAB_CLIENT_ID=application-id-from-step-2
GITLAB_CLIENT_SECRET=secret-from-step-2
INITIAL_INSTANCE_ADMIN=your-gitlab-username
```

### 4️⃣ Start Docker Containers
```bash
docker-compose -f docker-compose.development.yml up -d --build
```

### 5️⃣ Make Yourself Admin
```bash
docker exec -it manytask_postgres psql -U postgres -d manytask
```

```sql
UPDATE users SET is_instance_admin = TRUE WHERE username = 'your-username';
\q
```

### 6️⃣ Create a Course
```bash
curl --fail -X POST \
  -H "Authorization: Bearer <COURSE_TOKEN>" \
  -H "Content-type: application/x-yaml" \
  --data-binary "@.manytask.example.yml" \
  "http://localhost:8081/api/<COURSE_NAME>/update_config"
```

### 7️⃣ Activate the Course
```bash
docker exec -it manytask_postgres psql -U postgres -d manytask
```

```sql
UPDATE courses SET status = 'IN_PROGRESS' WHERE name = '<COURSE_NAME>';
\q
```

### 8️⃣ Open Manytask
🌐 [http://localhost:8081](http://localhost:8081)

### 9️⃣ Done! 🎉
Your local Manytask instance is ready!

---

## 📚 Need More Details?

See the [Full Local Development Guide](docs/local_development.md) for:
- Troubleshooting tips
- Useful commands
- Database queries
- Advanced configuration

---

## 🛠️ Useful Commands

```bash
# View logs
docker-compose -f docker-compose.development.yml logs -f

# Restart
docker-compose -f docker-compose.development.yml restart

# Stop
docker-compose -f docker-compose.development.yml down

# Access database
docker exec -it manytask_postgres psql -U postgres -d manytask
```

---

## ❓ Problems?

**Port 8081 already in use?**
→ Change port in `docker-compose.development.yml`

**GitLab OAuth error?**
→ Check `GITLAB_CLIENT_ID` and `GITLAB_CLIENT_SECRET` in `.env`

**Course not showing?**
→ Make sure course status is `IN_PROGRESS` in database

More help: [Troubleshooting Section](docs/local_development.md#troubleshooting)
