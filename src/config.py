import os
import pathlib

import openai


MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4-1106-preview')
DB_PATH = pathlib.Path(__file__).parent / 'db.sqlite3'
openai.api_key  = os.environ['OPENAI_API_KEY']
API_TOKEN = os.environ['TOKEN']
