# Production

On this page you can find documentation on how to run `manytask` itself  
Note: Please first refer to the [system setup documentation](./system_setup.md)


There are different varints how to set up manytask for you  


## Pre-setup 

First you need to obtain you server with static ip to host manytask (or set up dynamic one).  
And set up dns record to point this ip.  

For example: `py.manytask.org` - domain for python course


## Deploy 

Than you need to set up manytask docker itself 


### Manually (recommended) 

Better option is to create some files in place and run manytask **without** cloning the repo.

The latest manytask image can be found at docker hub: https://hub.docker.com/r/manytask/manytask

1. Create docker/docker-compose script with latest manytask version  
   Note: Best practice is to use version tag (e.g. `manytask/manytask:1.3.4`) **not** `latest` tag

   See [docker-compose.production.yml](../docker-compose.production.yml) file as an example  
   ```shell
   curl -JL https://raw.githubusercontent.com/yandexdataschool/manytask/main/docker-compose.development.yml -o docker-compose.yml 
   ```
 

2. Create `.env` file with production environment  

   See [.env.example](../.env.example) as an example
   ```shell
   curl -JL https://raw.githubusercontent.com/yandexdataschool/manytask/main/.env.example -o .env
   ```

3. Setup `certbot` to update https certificates   
   
   If you are using [docker-compose.production.yml](../docker-compose.production.yml) example, it's already set up.


### From repo (not recommended)

You can use this repo to setup manytask in production mode 

1. Copy latest manytask repo
    ```shell
    git clone https://github.com/yandexdataschool/manytask
    ```
   
2. Copy and fill `.env` file
    ```shell
    cp .env.example .env
    nano .env
    ```

#### Docker build (manytask only)
```shell
docker build --tag manytask:build .
docker stop manytask && docker rm manytask || true
docker run \
    -d \
    --name manytask \
    --restart always \
    --publish "5050:5050" \
    --env-file .env \
    manytask:build && docker logs -f manytask
```

#### Docker registry (manytask only)
```shell
docker pull manytask:latest
docker stop manytask && docker rm manytask || true
docker run \
    -d \
    --name manytask \
    --restart always \
    --publish "5050:5050" \
    --env-file .env \
    manytask:latest && docker logs -f manytask
```


#### Docker-compose (manytask with certs)
```shell
docker-compose -f docker-compose.production.yml up -d
docker-compose -f docker-compose.production.yml logs -f
```


## Setup 

Just after deploy the manytask will show `not_ready` page.  
So first you need to push `.deadlines.yml` and `.course.yml` files via api requests from your repo.

Here is how you can make it
```shell
curl --fail --silent -X POST -H "Authorization: Bearer $TESTER_TOKEN"
     -H "Content-type: application/x-yaml" --data-binary "@tests/.course.yml"
     "https://py.manytask.org/api/update_course_config"
curl --fail --silent -X POST -H "Authorization: Bearer $TESTER_TOKEN"
     -H "Content-type: application/x-yaml" --data-binary "@tests/.deadlines.yml"
     "https://py.manytask.org/api/update_deadlines"
```
Please, refer to the example files and api docs. 
