if __name__ == "__main__":  # pragma: no cover
    import logging

    import uvicorn

    from bridge import log
    from bridge.api import AppFactory

    logger = logging.getLogger(__name__)
    log.init()
    logger.info("Started.")
    app_factory = AppFactory()
    uvicorn.run(app_factory(), log_config=None, ws="websockets")
    logger.info("Exited.")
