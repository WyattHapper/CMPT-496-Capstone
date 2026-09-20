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
    # Attach the forwarder to this module's own logger, never the root
    # logger: root also carries INFO records from chromadb, httpx,
    # langchain and friends, and those would be emitted on stdout as
    # bogus progress messages for the frontend to display.
    logger.propagate = False

    # Avoid adding the handler twice
    if any(isinstance(h, FrontendProgressHandler) for h in logger.handlers):
        return

    logger.addHandler(FrontendProgressHandler())

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

def pipeline_progress(stage, percent):

    print(
        json.dumps({
            "type": "pipeline_progress",
            "stage": stage,
            "progress": percent
        }),
        flush=True
    )