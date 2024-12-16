import logging


def init_logging(ip, port, enable_remote, level = logging.INFO):
    logging.basicConfig(
        filename=f'logs/{ip}-{port}-app.log', level=level,
        format=f'%(asctime)s - {ip}:{port} - %(name)s - %(levelname)s - %(message)s',
    )

    if enable_remote:
        import ecs_logging
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(f'logs/{ip}-{port}-app.log.json')
        handler.setFormatter(ecs_logging.StdlibFormatter(extra={"node": f"{ip}:{port}"}))
        logger.addHandler(handler)
