import json
import traceback

import openai

from config import MODEL
from constants import OPENAI_FUNCTION_SCHEMA
from utils import unwrap_content, define_function, NoDefaults


def describe_function(code):
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": (
                f"Describe this python function: {code} in this schema {OPENAI_FUNCTION_SCHEMA}. "
                "I want only json in response, nothing else"
            )
        }]
    )
    return unwrap_content(response['choices'][0]['message']['content'], 'json')


def craft_incantation(text):
    messages = [{
        "role": "user",
        "content": (
            "Write a python function according to the request.  I want only"
            " python code in response, nothing else.  Put all necessary import"
            " within function's body, don't comment the code  and don't do any"
            f" exception handling unless it's necessary.  fRequest: {text}"
        )
    }]
    response = openai.ChatCompletion.create(model=MODEL, messages=messages)
    messages.append({"role": "assistant", "content": response['choices'][0]['message']['content']})

    last_e = None
    for i in range(3):
        code = unwrap_content(response['choices'][0]['message']['content'], 'python')
        code = NoDefaults.in_(code)
        try:
            name, _ = define_function(code)
            return name, code
        except Exception as e:
            last_e = e
            messages.append({
                "role": "assistant",
                "content": (
                    f"{''.join(traceback.format_exception(e))}\n"
                    "Fix this error. I want only python code in response, nothing else."
                )
            })
            continue
    else:
        raise last_e


def get_incantation_data():
    from models import Incantation

    return {
        incantation.name: {
            'code': incantation.code,
            'schema': json.loads(incantation.schema),
            'overrides': json.loads(incantation.overrides),
            'object': incantation,
        }
        for incantation in Incantation.select()
    }


def wish(text):
    incantations = get_incantation_data()
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=[{"role": "user", "content": text}],
        tools=[value['schema'] for value in incantations.values()],
        tool_choice="auto",
    )
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    if tool_calls:
        incantation = incantations[tool_calls[0].function['name']]
        _, func = define_function(incantation['code'])
        args = json.loads(tool_calls[0].function.arguments)
        try:
            return func(**args)
        except Exception as e:
            return incantation['object'], tool_calls[0].function.arguments, e


def fix(mishap):
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=[{"role": "user", "content": (
            "I need you to fix python function. I will provide it's code, call"
            " arguments formatted in some json schema and error traceback. Fix"
            " this error. I want only python code in response, nothing else."
            f" Code:\n{mishap.code}\nArguments:\n{mishap.request}\n"
            f"Traceback:\n{mishap.traceback}"
        )}],
    )
    code = unwrap_content(response['choices'][0]['message']['content'], 'python')
    try:
        define_function(code)
        return code
    except Exception as e:
        return e
