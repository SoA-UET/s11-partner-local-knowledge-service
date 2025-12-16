# NOTE: you can modify this file as appropriate.

from flask import Blueprint
from flask_restx import Api

v1 = Blueprint("v1", __name__, url_prefix="/api/v1")

_api = Api(
    v1,
    title='Version 1',
    version='1',
    description='The first stable version.',
)

from .conversations import api as conversations_api
from .packages import api as packages_api
from .faqs import api as faqs_api
from .file_imports import api as file_imports_api

_api.add_namespace(conversations_api)
_api.add_namespace(packages_api)
_api.add_namespace(faqs_api)
_api.add_namespace(file_imports_api)
