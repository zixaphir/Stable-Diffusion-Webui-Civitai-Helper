""" -*- coding: UTF-8 -*-
handle msg between js and python side
"""
import json
from . import util

# action list
JS_ACTIONS = (
    "open_url",
    "add_trigger_words",
    "use_preview_prompt",
    "dl_model_new_version",
    "rename_card",
    "remove_card"
)

PY_ACTIONS = (
    "open_url",
    "rename_card",
    "remove_card"
)


def parse_js_msg(msg):
    """
    handle request from javascript
    parameter: msg - msg from js as string in a hidden textbox
    return: dict for result
    """
    util.printD("Start parse js msg")
    msg_dict = json.loads(msg)

    # in case client side run JSON.stringify twice
    if isinstance(msg_dict, str):
        msg_dict = json.loads(msg_dict)

    action = msg_dict.get("action", "")
    if not action:
        util.printD("No action from js request")
        return None

    if action not in JS_ACTIONS:
        util.printD(f"Unknown action: {action}")
        return None

    util.printD("End parse js msg")

    return msg_dict


def build_py_msg(action:str, content:dict):
    """
    build python side msg for sending to js
    parameter: content dict
    return: msg as string, to fill into a hidden textbox
    """
    util.printD("Start build_msg")
    if not (content and action and action in PY_ACTIONS):
        util.indented_msg(
            f"""
            Could not run action on content:
            {action=}
            {content=}
            """
        )
        return None

    msg = {
        "action" : action,
        "content": content
    }

    util.printD("End build_msg")
    return json.dumps(msg)
