if __name__ == "__main__":  # pragma: no cover
    import logging

    import uvicorn

    from bridge import log
    from bridge.api import app

    logger = logging.getLogger(__name__)
    log.init()
    logger.info("Started.")
    uvicorn.run(app, log_config=None)
    logger.info("Exited.")
