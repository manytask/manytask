# Production

On this page you can find documentation on how to run `manytask` itself  
Note: Please first refer to the [system setup documentation](./system_setup.md)


There are different varints how to setup manytask for you  

## Deploy 

### Manually (recommended) 

Better option is to create some files in place and run manytask **without** cloning the repo.

The latest manytask image can be found at docker hub: https://hub.docker.com/r/manytask/manytask

1. Create docker/docker-compose script with latest manytask version  
   See [docker-compose.production.yml](../docker-compose.production.yml) file as an example  
   Note: Best practice is to use version tag (e.g. `manytask/manytask:1.3.4`) **not** `latest` tag
 

2. Create `.env` file with production environment  
   See [.env.example](../.env.example) as an example


3. Setup `certbot` to update https certificates    


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
docker-compose -f docker-compose.production.yml up --build
```


## Setup 

Just after deploy the manytask will show `not_ready` page.  
So first you need to push `.deadlines.yml` and `.course.yml` files via api requests from your repo.

Please, refer to the example files and api docs. 
