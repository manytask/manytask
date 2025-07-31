# Development guide

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