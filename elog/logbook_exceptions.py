class LogbookError(Exception):
    """ Parent logbook exception."""
    pass


class LogbookAuthenticationError(LogbookError):
    """ Raise when problem with username and password."""
    pass

class LogbookServerTimeout(LogbookError):
    """ Raise when the request to the logbook server timeouts. """

class LogbookServerProblem(LogbookError):
    """ Raise when problem accessing logbook server."""
    pass


class LogbookMessageRejected(LogbookError):
    """ Raised when manipulating/creating message was rejected by the server or there was problem composing message."""
    pass


class LogbookInvalidMessageID(LogbookMessageRejected):
    """ Raised when there is no message with specified ID on the server."""
    pass


class LogbookInvalidAttachmentType(LogbookMessageRejected):
    """ Raised when passed attachment has invalid type."""
    pass
