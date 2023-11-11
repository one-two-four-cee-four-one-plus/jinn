import json
import inspect
import sqlite3

import macaron
from config import DB_PATH
from services import craft_incantation, describe_function, fix
from utils import define_function, ReplaceVariables


class BaseModel:
    __tables = []

    def __init_subclass__(cls):
        cls.__tables.append(cls)

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


class Master(macaron.Model, BaseModel):
    moniker = macaron.CharField()
    code_phrase = macaron.CharField()

    _DDL_SQL = """
        CREATE TABLE IF NOT EXISTS master (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moniker TEXT,
            code_phrase TEXT
        )
    """

    @property
    def master_id(self):
        return self.id

    @master_id.setter
    def master_id(self, value):
        self.id = value


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
            FOREIGN KEY (master_id) REFERENCES master(id)
        )
    """

    @classmethod
    def craft(cls, text):
        name, code = craft_incantation(text)
        master = Master.get(1)
        return master.incantations.append(
            request=text,
            name=name,
            code=code,
            schema=describe_function(code),
            overrides='{}'
        )

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
        self.schema = describe_function(self.code)
        self.save()


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
        if not isinstance(result, Exception):
            incantation = self.incantation
            incantation.code = result
            incantation.schema = describe_function(result)
            incantation.save()
            return True
