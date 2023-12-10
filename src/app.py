import os
import json
import traceback

import bottle
import macaron
import canister
from config import DB_PATH, LOG_PATH
from models import BaseModel, Master, Incident, Config


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


class HTMLDecorator:
    def __init__(self, css=False, center=False):
        self.css = css
        self.center = center

    def __call__(self, func):

        def wrapper(*args, **kwargs):
            ret = func(*args, **kwargs)

            if isinstance(ret, str):
                return f'''
                <html>
                <head>
                    <link href="https://iosevka-webfonts.github.io/iosevka/iosevka.css" rel="stylesheet"/>
                    <style>{Config.get_value('css')}</style>
                    <title>Jinn</title>
                </head>
                <body>
                    {ret}
                </body>
                </html>
                '''
            else:
                return ret

        return wrapper


html = HTMLDecorator
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
@html()
def login_view():
    return bottle.template('''
        <p>{{error}}</p>
        <form action="/login" method="post">
            <input type="text" name="username" />
            <input type="password" name="password" />
            <input type="submit" value="Login" />
        </form>
    ''', error=bottle.request.query.get('error', ''))


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
@html()
def config_view():
    return bottle.template('''
    <a href="/">back</a>

    % for config in configs:
        <form action="/config/{{config.key}}" method="post">
            <label for="value">{{config.key}}</label>
            <input type="text" name="value" value="{{config.value}}" />
            <input type="submit" value="Update" />
        </form>
    % end

    % for master in masters:
        <form action="/flip_verification/{{master.id}}" method="post">
            <label for="value">{{master.moniker}}</label>
            <input type="submit" value="{{'Verify' if master.verified == 0 else 'Unverify'}}" />
        </form>
    % end
    ''', configs=Config.editable(), masters=Master.select('admin=?', [False]))


@bottle.post('/config/<key>')
def config_view(key):
    value = bottle.request.forms.get('value')
    Config.set_value(key, value)
    return bottle.redirect('/config')


@bottle.post('/flip_verification/<id>')
def flip_verification_view(id):
    master = Master.get(id)
    master.verified = not master.verified
    master.save()
    return bottle.redirect('/config')


@bottle.get('/log')
@html()
def log_view():
    with open(LOG_PATH, 'rt') as f:
        return f.read().replace('\n', '<br>').replace(' ', '&nbsp;')


@bottle.get('/')
@html()
def index():
    return bottle.template('''
    <a href="/incantations">incantations</a>
    % if master.admin:
        <a href='/config'>config</a>
        <a href='/log'>log</a>
    % end
    <a href="/logout">logout</a>
    % if Config.check('manual_incantation_crafting'):
        <form action="/incantation" method="post">
            <input type="submit" value="I wish to be able to" />
            <input type="text" name="text" />
        </form>
    % end
    <form action="/wish" method="post" id="form">
        <input type="submit" value="I wish to" />
        <input type="text" name="text" style="width: 80%;"/>
    </form>
    ''', Config=Config, master=master())



@bottle.get('/incantations')
@html()
def incantations_view():
    return bottle.template('''
        <a href="/">back</a>
        <ul>
        % for incantation in incantations:
            <li>
                <a href="/incantation/{{incantation.id}}">{{incantation.name}}</a>
                <a href="/incantation/{{incantation.id}}/delete">delete</a>
                <p>{{incantation.description}}</p>
            </li>
        % end
        </ul>
    ''', incantations=master().incantations, json=json)


@bottle.post('/incantation')
def craft_incantation_view():
    text = bottle.request.forms.get('text')
    incantation = master().craft_incantation(text)
    if isinstance(incantation, Exception):
        Incident.create(
            type='craft',
            traceback=''.join(traceback.format_exception(incantation, limit=-2))
        )
        return f'''
            <a href="/">back</a>
            <p>{incantation}</p>
        '''
    return bottle.redirect(f'/incantation/{incantation.id}')


@bottle.get('/incantation/<id>')
@html()
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
    incantation.mishaps.delete()
    incantation.delete()
    return bottle.redirect('/incantations')


@bottle.post('/wish')
@html()
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
            return bottle.template('''
                <a href="/">back</a>
                <p>{{result}}</p>
            ''', result=result)


@bottle.get('/mishap/<id>/fix')
def mishap_fix_view(id):
    mishap = master().mishap(id)
    result = mishap.fix()
    if isinstance(result, Exception):
        return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')
    else:
        return bottle.redirect(f'/incantation/{mishap.incantation.id}')


@bottle.get('/mishap/<id>/retry')
@html()
def mishap_retry_view(id):
    mishap = master().mishap(id)
    result = mishap.retry()
    if isinstance(result, Exception):
        return bottle.redirect(f'/incantation/{mishap.incantation.id}?mishap=true')
    else:
        return bottle.template('''
            <a href="/">back</a>
            <p>{{result}}</p>
        ''', result=result)


@bottle.get('/mishap/<id>/erase')
def mishap_erase_view(id):
    mishap = master().mishap(id)
    mishap.delete()
    return bottle.redirect(f'/incantation/{mishap.incantation.id}')


@bottle.get('/mishap/<id>/fix_and_retry')
@html()
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
            return bottle.template('''
                <a href="/">back</a>
                <p>{{result}}</p>
            ''', result=result)


@bottle.post('/api/wish')
def api_wish_view():
    input_format, voice_in = bottle.request.headers.get('Content-Type'), False
    output_format, voice_out = bottle.request.headers.get('Accept'), False

    if input_format == 'application/json':
        text = json.loads(bottle.request.body.read().decode('utf-8'))['text']
    elif input_format.startswith('audio/'):
        text = bottle.request.body.read()
        voice_in = True

    if output_format.startswith('audio/'):
        bottle.response.content_type = 'audio/mpeg'
        bottle.response.headers['Content-Disposition'] = 'inline; filename="response.mp3"'
        voice_out = True

    match api_master().wish(text, voice=voice_in):
        case incantation, request, exception:
            incantation.mishaps.append(
                request=request,
                code=incantation.code,
                traceback=''.join(traceback.format_exception(exception, limit=-2))
            )
            return (api_master().tts if voice_out else str)(f'Error: {exception}')
        case result:
            return (api_master().tts if voice_out else str)(result)


if __name__ == '__main__':
    BaseModel.create_tables()
    Master.fetch(
        os.environ.get('USERNAME', 'alladin'),
        os.environ.get('PASSWORD', 'open_sesame'),
        admin=True
    )
    bottle.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
