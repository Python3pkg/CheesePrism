from cheeseprism.index import IndexManager


def includeme(config):
    for name, func in list(request_funcs().items()):
        reify = not getattr(func, 'skip_reify', False)
        config.add_request_method(func, name=name, reify=reify)


def request_funcs():
    """
    Returns a map of functions to apply to the request

    ATT: No variables can be assigned for this work.
    """
    def settings(request):
        return request.registry.settings

    def file_root(request):
        return request.index.path

    def index(request):
        return IndexManager.from_registry(request.registry)

    def index_data_path(request):
        return request.index.datafile_path

    def index_data(request):
        return request.index.data_from_path(request.index.path \
                                            / request.index_data_path)

    return locals()
