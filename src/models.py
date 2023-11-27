import json
import inspect
import sqlite3
import string
import random
import hashlib
import traceback

import macaron
from config import DB_PATH
from services import craft_incantation, describe_function, wish, fix
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

    def incantations(self):
        return Incantation.select("master_id=?", [self.id])

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
        name, code = craft_incantation(text)
        return self.incantations.append(
            request=text,
            name=name,
            code=code,
            schema=describe_function(code),
            overrides='{}'
        )

    def _wish(self, text, allow_craft=False):
        incantations = {
            incantation.name: {
                'code': incantation.code,
                'schema': json.loads(incantation.schema),
                'overrides': json.loads(incantation.overrides),
                'object': incantation,
            }
            for incantation in Incantation.select("master_id=? OR public=TRUE", [self.id])
        }
        return wish(text, incantations, allow_craft=allow_craft)

    def wish(self, text):
        match ret := self._wish(text, allow_craft=True):
            case None:
                return ret
            case tool_text if isinstance(ret, str):
                self.craft_incantation(tool_text)
                return self._wish(text, allow_craft=False)
            case _:
                return ret


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

    def update_overrides(self, new_overrides):
        overrides = {}
        for key, value in new_overrides.items():
            if value:
                overrides[key] = value
        self.overrides = json.dumps(overrides)
        self.code = ReplaceVariables.in_(self.name, self.code, overrides)
        new_schema = json.loads(self.schema)
        for key in overrides:
            new_schema['function']['parameters']['properties'].pop(key, None)
            new_schema['function']['parameters']['required'].remove(key)
        self.schema = json.dumps(new_schema)
        self.save()

    @property
    def description(self):
        return json.loads(self.schema)['function']['description']


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
        result = fix(self)
        if isinstance(result, Exception):
            return result
        else:
            incantation = self.incantation
            incantation.code = result
            incantation.schema = describe_function(result)
            incantation.save()
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
        )
        for key, value in initial_config:
            if cls.get_value(key) is None:
                cls.set_value(key, value)
