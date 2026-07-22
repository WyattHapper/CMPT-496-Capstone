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

def progress(message, percent=None, step_complete=False):

    data = {
        "type": "progress",
        "stage": message
    }

    if percent is not None:
        data["progress"] = percent

    if step_complete:
        data["step_complete"] = True


    print(
        json.dumps(data),
        flush=True
    )

    logger.info(message)

def pipeline_progress(stage, percent):

    print(
        json.dumps({
            "type": "pipeline_progress",
            "stage": stage,
            "progress": percent
        }),
        flush=True
    )