import logging 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(filename)s - %(lineno)03d - %(levelname)s - %(message)s'
)

logger = logging.getLogger(name='[neuralmap]')

if __name__ == '__main__':
    logger.info('...[neuralmap]...')