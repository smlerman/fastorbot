class IRCCallback(object):
    def __init__(self, method, arguments=dict()):
        self.method = method
        self.arguments = arguments
