import logging

from flask import Blueprint


logger = logging.getLogger(__name__)
bp = Blueprint('web', __name__)


@bp.get('/')
def index():
    return 'Hello world!'

