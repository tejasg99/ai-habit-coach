import logging

from app.core.request_context import request_id_var

_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
_installed = False


def configure_logging() -> None:
    global _installed
    if not _installed:
        previous = logging.getLogRecordFactory()

        def factory(*args, **kwargs):
            record = previous(*args, **kwargs)
            record.request_id = request_id_var.get()  # every log record gets the current id
            return record

        logging.setLogRecordFactory(factory)
        _installed = True
    logging.basicConfig(level=logging.INFO, format=_FORMAT)
