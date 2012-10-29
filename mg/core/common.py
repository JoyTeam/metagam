from mg.core.cass import CassandraObject, CassandraObjectList
import logging

class StaticUploadError(Exception):
    "Error uploading object to the static server"
    pass

class DoubleResponseError(Exception):
    "start_response called twice on the same request"
    pass

class WebResponse(Exception):
    def __init__(self, content):
        self.content = content

class HookFormatError(Exception):
    "Invalid hook format"
    pass

class HandlerPermissionError(Exception):
    "Permission checks on the hook handler failed"
    pass

class DownloadError(Exception):
    "Failed Module().download()"
    pass

class Loggable(object):
    def __init__(self, fqn):
        self.fqn = fqn

    @property
    def logger(self):
        try:
            return self._logger
        except AttributeError:
            self._logger = logging.getLogger(self.fqn)
            return self._logger

    def log(self, level, msg, *args):
        logger = self.logger
        if logger.isEnabledFor(level):
            logger.log(level, msg, *args)

    def debug(self, msg, *args):
        self.logger.debug(msg, *args)

    def info(self, msg, *args):
        self.logger.info(msg, *args)

    def warning(self, msg, *args):
        self.logger.warning(msg, *args)

    def error(self, msg, *args):
        self.logger.error(msg, *args)

    def critical(self, msg, *args):
        self.logger.critical(msg, *args)

    def exception(self, exception, *args):
        self.logger.exception(exception, *args)
