import os
import pathlib

DATA_PATH = pathlib.Path(os.environ.get('DATA_PATH', '/var/www/data'))
DB_PATH = DATA_PATH / 'db.sqlite3'
LOG_PATH = DATA_PATH / 'log.txt'
