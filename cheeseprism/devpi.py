"""
Upload callback that uploads packages to devpi
"""

import logging
import subprocess

logger = logging.getLogger(__name__)


def upload(uploaded_file):
    logger.info(
        'devpi.upload: uploaded_file = %r',
        uploaded_file)

    cmd = ['devpi', 'login', '--password=monkey', 'monkey']
    logger.info('Logging into devpi...')
    logger.info('cmd = %r', cmd)
    ret = subprocess.call(cmd)
    if ret:
        logger.error('devpi login failed')
        return
    logger.info('Logged into devpi.')

    cmd = ['devpi', 'upload', uploaded_file]
    logger.info('Uploading %s to devpi...', uploaded_file)
    logger.info('cmd = %r', cmd)
    ret = subprocess.call(cmd)
    if ret:
        logger.error('devpi upload failed')
        return
    logger.info('Uploaded %s to devpi.', uploaded_file)
