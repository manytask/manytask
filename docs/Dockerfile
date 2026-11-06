FROM node:24 AS docs_builder

WORKDIR /docs
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build -- --output /html


FROM nginx AS docs
COPY --from=docs_builder /html /usr/share/nginx/html
