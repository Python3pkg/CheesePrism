from cheeseprism.index import IndexManager
from path import path
from pyramid.security import unauthenticated_userid


def includeme(config):
    for name, func in request_funcs().items():
        reify = not getattr(func, 'skip_reify', False)
        config.add_request_method(func, name=name, reify=reify)


def request_funcs():
    """
    Returns a map of functions to apply to the request

    No variables can be assigned for this work.
    """
    def userid(request):
        return unauthenticated_userid(request)
    userid.skip_reify = True

    def settings(request):
        return request.registry.settings


    def index_templates(request):
        return request.registry.settings['cheeseprism.index_templates']


    def file_root(request):
        return path(request.registry.settings['cheeseprism.file_root'])


    def index(request):
        return IndexManager.from_settings(request.settings)


    def index_data_path(request):
        return request.index.datafile_path


    def index_data(request):
        return request.index.data_from_path(request.file_root / request.index_data_path)


    def includeme(config):
        config.add_request_method()

    return locals()
