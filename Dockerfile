FROM python:3.12-slim

RUN apt-get update && apt-get install --yes curl

WORKDIR /app
ENV PYTHONPATH "${PYTHONPATH}:/app:/app/manytask"

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY ./manytask/ /app/manytask
COPY VERSION /app/VERSION

ENV CACHE_DIR=/cache SOLUTIONS_DIR=/solutions
VOLUME ["/cache", "/solutions"]

CMD python -m gunicorn \
    --bind 0.0.0.0:5050 \
    --workers 4 \
    --threads 2 \
    "manytask:create_app()"
#    --worker-class gthread \
#    --access-logfile - \
#    --access-logformat "%(t)s %({Host}i)s %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\" %(L)s %(b)s \"%(U)s\" \"%(q)s\"" \
#    --error-logfile -
