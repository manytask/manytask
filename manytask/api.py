import logging

from flask import Blueprint


logger = logging.getLogger(__name__)
bp = Blueprint('api', __name__, url_prefix='/api')


@bp.get('/test')
def index():
    return 'test'

