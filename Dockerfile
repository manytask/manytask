FROM python:3.12-alpine

RUN apk update && apk add --no-cache \
    curl \
    && rm -rf /var/cache/apk/*

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY ./manytask/ /app/manytask
COPY VERSION /app/VERSION

ENV CACHE_DIR=/cache SOLUTIONS_DIR=/solutions PYTHONPATH="${PYTHONPATH}:/app:/app/manytask"
VOLUME ["/cache", "/solutions"]

EXPOSE 5050

CMD python -m gunicorn \
    --bind 0.0.0.0:5050 \
    --workers 4 \
    --threads 2 \
    "manytask:create_app()"
#    --worker-class gthread \
#    --access-logfile - \
#    --access-logformat "%(t)s %({Host}i)s %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\" %(L)s %(b)s \"%(U)s\" \"%(q)s\"" \
#    --error-logfile -
