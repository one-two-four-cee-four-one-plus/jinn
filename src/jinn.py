import json
import inspect
import traceback

import bottle
import macaron
import canister
from config import DB_PATH
from models import BaseModel, Master, Incident, Config
from utils import define_function
from services import wish


bottle.install(macaron.MacaronPlugin(DB_PATH))
bottle.install(canister.Canister())


def require_auth(func):
    def wrapper(*args, **kwargs):
        if bottle.request.path.startswith('/api'):
            m = api_master()
        elif bottle.request.path.startswith('/login'):
            return func(*args, **kwargs)
        else:
            m = master()

        if not m:
            return bottle.redirect('/login?error=unauthorized')
        if not m.verified and not m.admin:
            return bottle.redirect('/login?error=unverified')

        return func(*args, **kwargs)
    return wrapper


bottle.install(require_auth)


def master():
    try:
        return Master.get(canister.session.data['user'])
    except (KeyError, Master.DoesNotExist):
        pass


def api_master():
    try:
        token = bottle.request.headers.get('Authorization').split(' ')[1]
        return Master.get("token=?", [token])
    except (IndexError, Master.DoesNotExist):
        pass


@bottle.get('/login')
def login_view():
    error = bottle.request.query.get('error', '')
    return f'''
        <p>{error}</p>
        <form action="/login" method="post">
            <input type="text" name="username" />
            <input type="password" name="password" />
            <input type="submit" value="Login" />
        </form>
    '''


@bottle.post('/login')
def login_view():
    username = bottle.request.forms.get('username')
    password = bottle.request.forms.get('password')
    if master := Master.fetch(username, password):
        canister.session.data['user'] = master.id
        return bottle.redirect('/')
    else:
        return bottle.redirect('/login?error=unauthorized')


@bottle.get('/logout')
def logout_view():
    canister.session.data.pop('user')
    return bottle.redirect('/login')


@bottle.get('/config')
def config_view():
    page = '<a href="/">back</a>'
    for config in Config.editable():
        page += f'''
            <form action="/config/{config.key}" method="post">
                <label for="value">{config.key}</label>
                <input type="text" name="value" value="{config.value}" />
                <input type="submit" value="Update" />
            </form>
        '''
    for master in Master.select('admin=?', [False]):
        page += f'''
        <form action="/flip_verification/{master.id}" method="post">
        <label for="value">{master.moniker}</label>
        <input type="submit" value="{'Verify' if master.verified == 0 else 'Unverify'}" />
        </form>
        '''
    return page


@bottle.post('/config/<key>')
def config_view(key):
    value = bottle.request.forms.get('value')
    config = Config.set_value(key, value)
    return bottle.redirect('/config')


@bottle.post('/flip_verification/<id>')
def flip_verification_view(id):
    master = Master.get(id)
    master.verified = not master.verified
    master.save()
    return bottle.redirect('/config')


@bottle.get('/')
def index():
    page = f'''
        <a href="/incantations">incantations</a>
        {"<a href='/config'>config</a>" if master().admin else ''}
        <a href="/logout">logout</a>
    '''
    if Config.check('manual_incantation_crafting'):
        page += f'''
            <form action="/incantation" method="post">
                <input type="submit" value="I wish to be able to" />
                <input type="text" name="text" />
            </form>
        '''
    page += f'''
        <form action="/wish" method="post">
            <input type="submit" value="I wish to" />
            <input type="text" name="text" />
        </form>
    '''
    return page


@bottle.get('/incantations')
def incantations_view():
    response = f'''
        <a href="/">back</a>
        <ul>
    '''
    for incantation in master().incantations:
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
    incantation = master().craft_incantation(text)
    if isinstance(incantation, Exception):
        Incident.create(
            type='craft',
            traceback=''.join(traceback.format_exception(e, limit=-2))
        )
        return f'''
            <a href="/">back</a>
            <p>{incantation}</p>
        '''
    return bottle.redirect(f'/incantation/{incantation.id}')


@bottle.get('/incantation/<id>')
def incantation_view(id):
    incantation = master().incantation(id)
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
        mishap_request = {k: v for k, v in json.loads(mishap.request).items() if k in incantation.parameters}
        mishaps += f'''
        <p>{mishap_request}</p>
        <pre>{mishap.traceback}</pre>
        <a href="/mishap/{mishap.id}/fix">fix</a>
        <a href="/mishap/{mishap.id}/retry">retry</a>
        <a href="/mishap/{mishap.id}/erase">erase</a>
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
    incantation = master().incantation(id)
    try:
        incantation.update_overrides(bottle.request.forms)
    except Exception as e:
        Incident.create(
            type='override',
            traceback=''.join(traceback.format_exception(e, limit=-2))
        )
    return bottle.redirect(f'/incantation/{id}')


@bottle.get('/incantation/<id>/delete')
def incantation_delete_view(id):
    incantation = master().incantation(id)
    incantation.delete()
    return bottle.redirect('/')


@bottle.post('/wish')
def wish_view():
    text = bottle.request.forms.get('text')
    match master().wish(text):
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
            {result}
            '''


@bottle.get('/mishap/<id>/fix')
def mishap_fix_view(id):
    mishap = master().mishap(id)
    result = mishap.fix()
    if isinstance(result, Exception):
        return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')
    else:
        return bottle.redirect(f'/incantation/{mishap.incantation.id}')


@bottle.get('/mishap/<id>/retry')
def mishap_retry_view(id):
    mishap = master().mishap(id)
    result = mishap.retry()
    if isinstance(result, Exception):
        return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')
    else:
        return f'''
            <a href="/">back</a>
            {result}
            '''

@bottle.get('/mishap/<id>/erase')
def mishap_erase_view(id):
    mishap = master().mishap(id)
    mishap.delete()
    return bottle.redirect(f'/incantation/{mishap.incantation.id}')


@bottle.get('/mishap/<id>/fix_and_retry')
def mishap_fix_and_retry_view(id):
    mishap = master().mishap(id)
    result = mishap.fix()
    if isinstance(result, Exception):
        return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')
    else:
        result = mishap.retry()
        if isinstance(result, Exception):
            return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')
        else:
            return f'''
            <a href="/">back</a>
            {result}
            '''


@bottle.post('/api/incantation')
def api_craft_incantation_view():
    text = json.loads(bottle.request.body.read().decode('utf-8'))['text']
    try:
        incantation = api_master().craft_incantation(text)
    except Exception as e:
        Incident.create(
            type='craft',
            traceback=''.join(traceback.format_exception(e, limit=-2))
        )
        return 'Error'
    return json.dumps({'id': incantation.id, 'name': incantation.name})


@bottle.post('/api/wish')
def api_wish_view():
    text = json.loads(bottle.request.body.read().decode('utf-8'))['text']
    match api_master().wish(text):
        case incantation, request, exception:
            incantation.mishaps.append(
                request=request,
                code=incantation.code,
                traceback=''.join(traceback.format_exception(exception, limit=-2))
            )
            return json.dumps({'error': str(exception)})
        case result:
            result = str(result) if len(str(result)) < 20 else str(result)[:20]
            return json.dumps({'result': result})


if __name__ == '__main__':
    BaseModel.create_tables()
    Master.fetch('alladin', 'open_sesame', admin=True)
    bottle.run(host='0.0.0.0', port=8080, debug=True)
