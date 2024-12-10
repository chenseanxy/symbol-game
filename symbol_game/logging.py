import logging

def init_logging(ip, port, level = logging.INFO):
    logging.basicConfig(
        filename=f'{ip}-{port}-app.log', level=level,
        format=f'%(asctime)s - {ip}:{port} - %(name)s - %(levelname)s - %(message)s',
    )
