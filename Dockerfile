FROM python:3.9-slim
WORKDIR /app
ENV PYTHONPATH "${PYTHONPATH}:/app:/app/manytask"

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY ./manytask/ /app/manytask

ENV CACHE_DIR=/cache SOLUTIONS_DIR=/cache
VOLUME ["/cache", "/solutions"]

CMD python -m gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --threads 4 \
    "manytask:create_app()"
#    --worker-class gthread \
#    --access-logfile - \
#    --access-logformat "%(t)s %({Host}i)s %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\" %(L)s %(b)s \"%(U)s\" \"%(q)s\"" \
#    --error-logfile -
