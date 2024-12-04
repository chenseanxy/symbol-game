import logging

def init_logging(path: str, level = logging.INFO):
    logging.basicConfig(filename=f'{path}-app.log', level=logging.INFO)
