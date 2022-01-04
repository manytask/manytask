FROM python:3.9-slim
WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY ./manytask /app

CMD gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --threads 4 \
    main:create_app
#    --worker-class gthread \
#    --access-logfile - \
#    --access-logformat "%(t)s %({Host}i)s %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\" %(L)s %(b)s \"%(U)s\" \"%(q)s\"" \
#    --error-logfile -
