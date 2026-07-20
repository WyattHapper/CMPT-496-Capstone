import json
import logging
logger = logging.getLogger(__name__)


class FrontendProgressHandler(logging.Handler):
    def emit(self, record):
        print(
            json.dumps({
                "type": "progress",
                "stage": record.getMessage()
            }),
            flush=True,
        )


def configure_progress_logging():
    root = logging.getLogger()

    # Avoid adding the handler twice
    if any(isinstance(h, FrontendProgressHandler) for h in root.handlers):
        return

    root.addHandler(FrontendProgressHandler())

def progress(message):
    logger.info("[PROGRESS] " + message)