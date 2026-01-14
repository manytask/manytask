# Local Development with Docker

This guide will help you set up and run Manytask locally using Docker Compose.

## Prerequisites

- Docker and Docker Compose installed
- Git installed
- Access to GitLab instance (request from [@artemzhmurov](https://t.me/artemzhmurov))

---

## Quick Start

### Step 1: Clone the Repository

```bash
git clone https://github.com/manytask/manytask.git
cd manytask
```

### Step 2: Request GitLab Access

Contact **[@artemzhmurov](https://t.me/artemzhmurov)** to get registered on [gitlab.manytask2.org](https://gitlab.manytask2.org).

### Step 3: Create GitLab OAuth Application

1. Go to GitLab Admin Area: [https://gitlab.manytask2.org/admin/applications](https://gitlab.manytask2.org/admin/applications)
2. Click **"New application"**
3. Fill in the form:
   - **Name**: `manytask-local` (or any name you prefer)
   - **Redirect URI**: `http://localhost:8081/login_finish`
   - **Trusted**: ✅ Yes
   - **Confidential**: ✅ Yes
   - **Scopes**: Select all scopes:
     - ✅ `api` - Access the API on your behalf
     - ✅ `read_user` - Read your personal information
     - ✅ `read_repository` - Allows read-only access to the repository
     - ✅ `sudo` - Perform API actions as any user in the system
     - ✅ `openid` - Authenticate using OpenID Connect
     - ✅ `profile` - Allows read-only access to the user's personal information using OpenID Connect
     - ✅ `email` - Allows read-only access to the user's primary email address using OpenID Connect
4. Click **"Save application"**
5. **Copy the Application ID and Secret** - you'll need them in the next step

### Step 4: Configure Environment Variables

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Open `.env` and fill in the following variables:

   ```bash
   # Flask secret key - generate a random string
   FLASK_SECRET_KEY=your-random-secret-key-here

   # GitLab configuration
   GITLAB_URL=https://gitlab.manytask2.org
   GITLAB_ADMIN_TOKEN=your-admin-token-here

   # OAuth credentials from Step 3
   GITLAB_CLIENT_ID=your-application-id-here
   GITLAB_CLIENT_SECRET=your-application-secret-here

   # Your GitLab username
   INITIAL_INSTANCE_ADMIN=your-gitlab-username

   # Database configuration (default values should work)
   DATABASE_URL=postgresql://adminmanytask:adminpass@postgres:5432/manytask
   DATABASE_URL_EXTERNAL=postgresql://adminmanytask:adminpass@localhost:5432/manytask
   ```

   > **Note**: You can get `GITLAB_ADMIN_TOKEN` from GitLab: Settings → Access Tokens → Create a token with all scopes

### Step 5: Start the Application

```bash
docker-compose -f docker-compose.development.yml up -d --build
```

This will start:

- PostgreSQL database on port `5432`
- Manytask application on [http://localhost:8081](http://localhost:8081)

### Step 6: Make Yourself an Admin

1. Connect to the PostgreSQL database:

   ```bash
   docker exec -it manytask_postgres psql -U postgres -d manytask
   ```

2. Update your user to be an instance admin:

   ```sql
   UPDATE users
   SET is_instance_admin = TRUE
   WHERE username = 'your-gitlab-username';
   ```

   You should see: `UPDATE 1`

3. Exit the database:
   ```sql
   \q
   ```

### Step 7: Create a Course

1. Prepare the course configuration:

   - Make sure you have a `.manytask.example.yml` file in the project root
   - Note your course token (you'll set it when creating the course)

2. Create the course using the API:

   ```bash
   curl --fail -X POST \
     -H "Authorization: Bearer <COURSE_TOKEN>" \
     -H "Content-type: application/x-yaml" \
     --data-binary "@.manytask.example.yml" \
     "http://localhost:8081/api/<COURSE_NAME>/update_config"
   ```

   Replace:

   - `<COURSE_TOKEN>` - with your course token
   - `<COURSE_NAME>` - with your course name (e.g., `test_course_2024`)

   > **Note**: You can also use the example from [curl_for_create_course.example](../curl_for_create_course.example)

### Step 8: Activate the Course

1. Connect to the database again:

   ```bash
   docker exec -it manytask_postgres psql -U postgres -d manytask
   ```

2. Update the course status:

   ```sql
   UPDATE courses
   SET status = 'IN_PROGRESS'
   WHERE name = '<COURSE_NAME>';
   ```

   You should see: `UPDATE 1`

3. Exit the database:
   ```sql
   \q
   ```

### Step 9: Access Manytask

Open your browser and go to [http://localhost:8081](http://localhost:8081)

You should now see your course in the web interface! 🎉

---

## Useful Commands

### View logs

```bash
docker-compose -f docker-compose.development.yml logs -f
```

### Stop the application

```bash
docker-compose -f docker-compose.development.yml down
```

### Restart the application

```bash
docker-compose -f docker-compose.development.yml restart
```

### Rebuild and restart

```bash
docker-compose -f docker-compose.development.yml up -d --build
```

### Access the database

```bash
docker exec -it manytask_postgres psql -U postgres -d manytask
```

---

## Troubleshooting

### Port 8081 is already in use

Change the port in `docker-compose.development.yml` or stop the service using that port.

### Cannot connect to database

Make sure PostgreSQL container is running:

```bash
docker ps
```

### GitLab OAuth error

- Double-check your `GITLAB_CLIENT_ID` and `GITLAB_CLIENT_SECRET` in `.env`
- Make sure the Redirect URI is exactly `http://localhost:8081/login_finish`
- Verify the application is marked as "Trusted" and "Confidential"

### Course not appearing

- Make sure you updated the course status to `IN_PROGRESS` in the database
- Check the course name matches exactly (case-sensitive)
- Try refreshing the page

---

## Next Steps

- Read [Development Guide](./dev.md) for more information on the codebase
- Check [API Documentation](./api.md) for API endpoints
- Learn about [Course Configuration](./course_as_code.md)

---
