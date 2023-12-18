import json
import inspect
import sqlite3
import string
import random
import hashlib
import traceback

import macaron
from config import DB_PATH
from services import craft_incantation, describe_function, wish, fix, adjust, stt, tts
from utils import define_function, ReplaceVariables


class BaseModel:
    __tables = []

    def __init_subclass__(cls):
        cls.__tables.append(cls)

    @classmethod
    def _after_create(cls):
        pass

    @classmethod
    def _create_table(cls):
        if not hasattr(cls, '_DDL_SQL'):
            return
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(cls._DDL_SQL)

    @classmethod
    def create_tables(cls):
        for table in cls.__tables:
            table._create_table()
            table._after_create()


class Master(macaron.Model, BaseModel):
    moniker = macaron.CharField()
    code_phrase = macaron.CharField()
    token = macaron.CharField()
    admin = macaron.IntegerField(min=0, max=1, default=0)
    verified = macaron.IntegerField(min=0, max=1, default=0)

    _DDL_SQL = """
        CREATE TABLE IF NOT EXISTS master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moniker TEXT,
            code_phrase TEXT,
            token TEXT,
            admin INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            UNIQUE(moniker)
        )
    """

    @property
    def master_id(self):
        return self.id

    @master_id.setter
    def master_id(self, value):
        self.id = value

    @classmethod
    def fetch(cls, moniker, code_phrase, admin=False):
        code_phrase = Config.get_value('code_phrase_salt') + code_phrase
        code_phrase = hashlib.sha256(code_phrase.encode('utf-8')).hexdigest()
        try:
            obj = cls.get("moniker=?", [moniker])
        except cls.DoesNotExist:
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            admin = 1 if admin else 0
            return cls.create(moniker=moniker, code_phrase=code_phrase, admin=admin, token=token)
        else:
            return obj if obj.code_phrase == code_phrase else None

    def incantation(self, id):
        try:
            return Incantation.get("master_id=? AND id=?", [self.id, id])
        except Incantation.DoesNotExist:
            pass

    def mishap(self, id):
        try:
            ret = Mishap.get("id=?", [id])
            if self.incantation(ret.incantation_id) is None:
                return None
            return ret
        except Mishap.DoesNotExist:
            pass

    def craft_incantation(self, text):
        name, code = craft_incantation(
            Config.get_value('openai_key'), Config.get_value('openai_model'),
            Config.get_value('craft_retries', 3), text
        )
        return self.incantations.append(
            request=text,
            name=name,
            code=code,
            schema=describe_function(
                Config.get_value('openai_key'), Config.get_value('openai_model'), code
            ),
            overrides='{}'
        )

    def _wish(self, text, allow_craft=False, call=True):
        incantations = {
            incantation.name: {
                'code': incantation.code,
                'schema': json.loads(incantation.schema),
                'overrides': json.loads(incantation.overrides),
                'object': incantation,
            }
            for incantation in self.incantations
        }
        return wish(
            Config.get_value('openai_key'), Config.get_value('openai_model'), text,
            incantations, allow_craft=allow_craft, call=call
        )

    def wish(self, text, voice=False):
        if voice:
            text = stt(Config.get_value('openai_key'), text)
        match ret := self._wish(text, allow_craft=True):
            case 'craft_incantation', tool_text:
                self.craft_incantation(tool_text)
                return self._wish(text, allow_craft=False)
            case incantation, args, error:
                return f'Error: {error} while executing {incantation.name}({", ".join(args)})'
            case _:
                return ret

    def tts(self, text):
        return tts(Config.get_value('openai_key'), text)

    def stt(self, audio):
        return stt(Config.get_value('openai_key'), audio)

    def prepare(self, text):
        match ret := self._wish(text, allow_craft=True, call=False):
            case 'craft_incantation', tool_text:
                text = f'craft_incantation("{json.loads(tool_text)["text"]}")'
                return {
                    'craft_incantation': json.loads(tool_text)['text'],
                    'wish': text,
                    'text': text,
                }
            case incantation, args:
                return {
                    'incantation': incantation['object'].id,
                    'args': args,
                    'text': f'{incantation["object"].name}{args})',
                }

    def craft_and_prepare(self, data):
        self.craft_incantation(data['craft_incantation'])
        incantation, args = self._wish(data['wish'], allow_craft=False, call=False)
        text = f'{incantation["object"].name}{", ".join(args)}'
        return {'incantation': incantation['object'].id, 'args': args, 'text': text}

    def execute(self, data):
        incantation = self.incantation(data['incantation'])
        return incantation.execute(data)

    def proceed(self, data):
        if 'result' in data:
            return data
        if 'craft_incantation' in data:
            return self.craft_and_prepare(data)
        elif 'incantation' in data:
            return self.execute(data)
        else:
            return self.prepare(data['text'])


class Incantation(macaron.Model, BaseModel):
    name = macaron.CharField()
    master = macaron.ManyToOne(Master, fkey='master_id', ref_key='id', related_name='incantations')
    request = macaron.CharField()
    code = macaron.CharField()
    schema = macaron.CharField()
    overrides = macaron.CharField()

    _DDL_SQL = """
        CREATE TABLE IF NOT EXISTS incantation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            master_id INTEGER,
            request TEXT,
            name TEXT,
            code TEXT,
            schema TEXT,
            overrides TEXT,
            public BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (master_id) REFERENCES master(id)
        )
    """

    @property
    def parameters(self):
        _, func = define_function(self.code)
        return inspect.getfullargspec(func).args

    @property
    def overrides_dict(self):
        return json.loads(self.overrides)

    def update_overrides(self, overrides):
        self.overrides = json.dumps(overrides) if isinstance(overrides, dict) else overrides
        self.save()

    def adjust(self, reason, update_schema=False):
        result = adjust(
            Config.get_value('openai_key'), Config.get_value('openai_model'),
            self.code, reason
        )
        if isinstance(result, Exception):
            return result
        self.code = result
        if update_schema:
            self.schema = describe_function(
                Config.get_value('openai_key'), Config.get_value('openai_model'), result
            )
        self.save()
        return self

    @property
    def description(self):
        return json.loads(self.schema)['function']['description']

    def redescribe(self):
        self.schema = describe_function(
            Config.get_value('openai_key'), Config.get_value('openai_model'), self.code
        )
        self.save()

    def execute(self, data):
        _, func = define_function(self.code)
        args = json.loads(data['args'])
        for key, value in json.loads(self.overrides).items():
            args[key] = value
        return {'result': func(**args)}


class Mishap(macaron.Model, BaseModel):
    incantation = macaron.ManyToOne(Incantation, fkey='incantation_id', ref_key='id', related_name='mishaps')
    request = macaron.CharField()
    code = macaron.CharField()
    traceback = macaron.CharField()

    _DDL_SQL = """
        CREATE TABLE IF NOT EXISTS mishap (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incantation_id INTEGER,
            request TEXT,
            code TEXT,
            traceback TEXT,
            FOREIGN KEY (incantation_id) REFERENCES incantation(id)
        )
    """

    def fix(self):
        result = fix(
            Config.get_value('openai_key'), Config.get_value('openai_model'),
            self.code, self.request, self.traceback
        )
        if isinstance(result, Exception):
            return result
        self.incantation.code = result
        self.incantation.schema = describe_function(
            Config.get_value('openai_key'), Config.get_value('openai_model'), result
        )
        self.incantation.save()
        return self

    def retry(self):
        # reload code
        incantation = Incantation.get("id=?", [self.incantation_id])
        try:
            _, func = define_function(incantation.code)
            arguments = set(inspect.getargspec(func).args)
            ret = func(**{k: v for k, v in json.loads(self.request).items() if k in arguments})
            Mishap.select("traceback=? AND code=?", [self.traceback, self.code]).delete()
            return ret
        except Exception as e:
            incantation.mishaps.append(
                request=self.request,
                code=incantation.code,
                traceback=''.join(traceback.format_exception(e, limit=-2))
            )
            return e


class Incident(macaron.Model, BaseModel):
    type = macaron.CharField()
    traceback = macaron.CharField()

    _DDL_SQL = """
        CREATE TABLE IF NOT EXISTS incident (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            traceback TEXT
        )
    """


class Config(macaron.Model, BaseModel):
    key = macaron.CharField()
    value = macaron.CharField()

    _DDL_SQL = """
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            value TEXT,
            UNIQUE(key)
        )
    """

    @classmethod
    def get_value(cls, key, default=None):
        try:
            return str(cls.get("key=?", [key]).value)
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_value(cls, key, value):
        try:
            obj = cls.get("key=?", [key])
        except cls.DoesNotExist:
            cls.create(key=key, value=value)
        else:
            obj.value = str(value)
            obj.save()

    @classmethod
    def check(cls, key):
        return cls.get_value(key) == '1'

    @classmethod
    def editable(cls):
        return cls.select("key NOT IN ('code_phrase_salt', 'admin')")

    @classmethod
    def _after_create(cls):
        from constants import CSS

        initial_config = (
            ('code_phrase_salt',
             ''.join(random.choices(string.ascii_letters + string.digits, k=32))),
            ('openai_key', '[FILL THIS IN]'),
            ('openai_model', 'gpt-4-1106-preview'),
            ('manual_incantation_crafting', '0'),
            ('craft_retries', '3'),
            ('css', CSS),
            ('registration_allowed', '0'),
        )
        for key, value in initial_config:
            if cls.get_value(key) is None:
                cls.set_value(key, value)
