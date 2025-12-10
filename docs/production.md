# Production

On this page you can find documentation on how to run `manytask` itself  
NB: Please first refer to the [system setup documentation](./system_setup.md)


There are different varints how to set up manytask for you  


## Pre-setup 

First you need to obtain you server with static ip to host manytask (or set up dynamic one).  
And set up dns record to point this ip.  

For example: `py.manytask.org` - domain for python course


## Deploy 

Then you need to set up manytask docker itself  

> 📘 **See also:** [Deploy guide](./deploy_guide.md) — пошаговая инструкция по деплою на удалённый сервер с настройкой базы данных и Instance Admin. 


### Manually (recommended) 

Better option is to create some files in place and run manytask **without** cloning the repo.

The latest manytask image can be found at docker hub: https://hub.docker.com/r/manytask/manytask

Here is the way you can go if you have 1 server with 1 manytask instance (1 course). If you have multiple, it's worth to separate nginx-proxy dockers.


1. Create docker/docker-compose script with latest manytask version  
   Note: Best practice is to use version tag (e.g. `manytask/manytask:9.9.9`) **not** `latest` tag

   See [docker-compose.production.yml](/docker-compose.production.yml) file as an example  
   ```shell
   curl -JL https://raw.githubusercontent.com/yandexdataschool/manytask/main/docker-compose.development.yml -o docker-compose.yml 
   ```

2. Create `.env` file with production environment  

   See [.env.example](../.env.example) as an example
   ```shell
   curl -JL https://raw.githubusercontent.com/yandexdataschool/manytask/main/.env.example -o .env
   ```

3. Setup `nginx-proxy`/`letencrypt`/`certbot` to update https certificates automatically  
   
   If you are using [docker-compose.production.yml](/docker-compose.production.yml) example, it's already set up.


### From repo (not recommended)

You can use this repo to set up manytask in production mode 

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
To fix the list of tasks and their deadlines, you first need to push `.manytask.yml` file via api requests from your repo. You can also use an example `tests/.manytask.test.yml` file from this repo.

Here is how you can make it
```shell
curl --fail --silent -X POST -H "Authorization: Bearer $MANYTASK_COURSE_TOKEN" -H        
     "Content-type: application/x-yaml" --data-binary "@tests/.manytask.test.yml" "https://py.manytask.org/api/update_config"
```
Please, refer to the example files and api docs. 


## How to build documentation

### Install NPM:

```bash
sudo apt install npm
```

### Install YFM and build:

```bash
sudo npm i @diplodoc/cli -g
```

### Build html from yml/md files:

```bash
yfm -i ./docs -o ./html --allow-custom-resources
```