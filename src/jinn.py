import json
import traceback

import bottle
import macaron
from config import DB_PATH, API_TOKEN
from models import BaseModel, Incantation, Mishap
from utils import define_function
from services import wish


bottle.install(macaron.MacaronPlugin(DB_PATH))


def require_auth(func):
    def wrapper(*args, **kwargs):
        auth = bottle.request.headers.get('Authorization')
        if auth != 'Bearer ' + API_TOKEN:
            bottle.abort(401, 'Unauthorized')
        return func(*args, **kwargs)
    return wrapper


@bottle.get('/')
def index():
    return f'''
        <a href="/incantations">incantations</a>
        <form action="/incantation" method="post">
            <input type="submit" value="I wish to be able to" />
            <input type="text" name="text" />
        </form>
        <form action="/wish" method="post">
            <input type="submit" value="I wish to" />
            <input type="text" name="text" />
        </form>
    '''


@bottle.get('/incantations')
def incantations_view():
    response = f'''
        <a href="/">back</a>
        <ul>
    '''
    for incantation in Incantation.all():
        description = json.loads(incantation.schema)['function']['description']
        response += f'''
            <li>
                <a href="/incantation/{incantation.id}">{incantation.name}</a>
                <a href="/incantation/{incantation.id}/delete">delete</a>
                <p>{description}</p>
            </li>
        '''
    return response + '</ul>'


@bottle.post('/incantation')
def craft_incantation_view():
    text = bottle.request.forms.get('text')
    incantation = Incantation.craft(text)
    return bottle.redirect(f'/incantation/{incantation.id}')


@bottle.get('/incantation/<id>')
def incantation_view(id):
    incantation = Incantation.get(id)
    form = f'<form action="/incantation/{id}/override" method="post">'
    for parameter in incantation.parameters:
        value = incantation.overrides_dict.get(parameter, '')
        form += f'''
            <label for="{parameter}">{parameter}</label>
            <input type="text" name="{parameter}" value="{value}" />
            <br />
        '''
    form += '<input type="submit" value="Update overrides" />'
    mishaps = ''
    for mishap in incantation.mishaps:
        mishaps += f'''
        <p>{mishap.request}</p>
        <pre>{mishap.traceback}</pre>
        <a href="/mishap/{mishap.id}/fix">fix</a>
        <a href="/mishap/{mishap.id}/fix_and_retry">fix & retry</a>
        '''

    return f'''
        <a href="/">back</a>
        <h1>{incantation.name}</h1>
        <p>{incantation.request}</p>
        <details>
            <summary>code</summary>
            <pre>{incantation.code}</pre>
        </details>
        <details>
            <summary>schema</summary>
            <pre>{incantation.schema}</pre>
        </details>
        <details>
            <summary>overrides</summary>
            {form}
        </details>
        {mishaps}
    '''


@bottle.post('/incantation/<id>/override')
def incantation_override_view(id):
    incantation = Incantation.get(id)
    incantation.update_overrides(bottle.request.forms)
    return bottle.redirect(f'/incantation/{id}')


@bottle.get('/incantation/<id>/delete')
def incantation_delete_view(id):
    incantation = Incantation.get(id)
    incantation.delete()
    return bottle.redirect('/')


@bottle.post('/wish')
def wish_view():
    text = bottle.request.forms.get('text')
    match wish(text):
        case incantation, request, exception:
            incantation.mishaps.append(
                request=request,
                code=incantation.code,
                traceback=''.join(traceback.format_exception(exception, limit=-2))
            )
            return bottle.redirect(f'/incantation/{incantation.id}?mishap=true')
        case result:
            return f'''
            <a href="/">back</a>
            <h1>Wish granted</h1>
            '''


@bottle.get('/mishap/<id>/fix')
def mishap_fix_view(id):
    mishap = Mishap.get(id)
    if mishap.fix():
        return bottle.redirect(f'/incantation/{mishap.incantation.id}')
    else:
        return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')


@bottle.get('/mishap/<id>/fix_and_retry')
def mishap_fix_and_retry_view(id):
    mishap = Mishap.get(id)
    if mishap.fix():
        # reload code
        incantation = Incantation.get(mishap.incantation.id)
        try:
            _, func = define_function(incantation.code)
            ret = func(**json.loads(mishap.request))
            Mishap.select("traceback=? AND code=?", [mishap.traceback, mishap.code]).delete()
            return f'''
            <a href="/">back</a>
            <h1>Wish granted</h1>
            '''
        except Exception as e:
            incantation.mishaps.append(
                request=mishap.request,
                code=incantation.code,
                traceback=''.join(traceback.format_exception(e, limit=-2))
            )
            return bottle.redirect(f'/incantation/{mishap.incantation.id}')
    else:
        return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')


@require_auth
@bottle.post('/api/incantation')
def api_craft_incantation_view():
    text = bottle.request.body.read().decode('utf-8')
    incantation = Incantation.craft(text)
    return bottle.redirect(f'/incantation/{incantation.id}')


@require_auth
@bottle.post('/api/wish')
def api_wish_view():
    text = bottle.request.body.read().decode('utf-8')
    match wish(text):
        case incantation, request, exception:
            incantation.mishaps.append(
                request=request,
                code=incantation.code,
                traceback=''.join(traceback.format_exception(exception, limit=-2))
            )
            return bottle.redirect(f'/incantation/{incantation.id}?mishap=true')
        case result:
            return str(result)


if __name__ == '__main__':
    BaseModel.create_tables()
    import sqlite3
    with sqlite3.connect(DB_PATH) as conn:
        result = conn.execute('SELECT * FROM master WHERE moniker=?', ('Alladin',))
        if not result.fetchone():
            conn.execute('''
            INSERT INTO master (moniker, code_phrase)
            VALUES ('Alladin', 'Open Sesame')
            ''')
    bottle.run(host='0.0.0.0', port=8080, debug=True)
