"""Production entry point, imported after Gunicorn's gevent worker patches the standard library."""

from grpc.experimental.gevent import init_gevent
from psycopg2.extensions import set_wait_callback
from psycopg2.extras import wait_select

from .main import create_app

# Both C drivers need to yield to other requests while waiting for network I/O.
init_gevent()
set_wait_callback(wait_select)
app = create_app()
