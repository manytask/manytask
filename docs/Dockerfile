FROM node:24 AS docs_builder

RUN npm i @diplodoc/cli -g

COPY . ./docs
RUN yfm -i ./docs -o ./html --allow-custom-resources


FROM nginx AS docs
COPY --from=docs_builder /html /usr/share/nginx/html
