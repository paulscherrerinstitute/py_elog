from elog.logbook import Logbook

def open(*args, **kwargs):
    """
    Will return a Logbook object. All arguments are passed to the logbook constructor.
    :param args:
    :param kwargs:
    :return: Logbook() instance
    """
    return(Logbook(*args, **kwargs))
