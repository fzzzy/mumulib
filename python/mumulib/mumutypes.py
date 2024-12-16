



class SpecialResponse(object):
    def __init__(self, asgi_send_dict, leaf_object):
        self.asgi_send_dict = asgi_send_dict
        self.leaf_object = leaf_object
