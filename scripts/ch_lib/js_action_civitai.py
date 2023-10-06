""" -*- coding: UTF-8 -*-
handle msg between js and python side
"""
import os
from pathlib import Path
import webbrowser
from modules.shared import opts
from . import util
from . import model
from . import civitai
from . import msg_handler
from . import downloader


def open_model_url(msg):
    """
    get civitai's model url and open it in browser
    parameter: model_type, search_term
    output: python msg
        - will be sent to hidden textbox then picked by js side
    """
    util.printD("Start open_model_url")

    output = ""
    result = msg_handler.parse_js_msg(msg)
    if not result:
        util.printD("Parsing js ms failed")
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]

    model_info = civitai.load_model_info_by_search_term(model_type, search_term)
    if not model_info:
        util.printD(f"Failed to get model info for {model_type} {search_term}")
        return ""

    if "modelId" not in model_info.keys():
        util.printD(f"Failed to get model id from info file for {model_type} {search_term}")
        return ""

    model_id = model_info["modelId"]
    if not model_id:
        util.printD(f"model id from info file of {model_type} {search_term} is None")
        return ""

    url = f'{civitai.URLS["modelPage"]}{model_id}'

    # msg content for js
    content = {
        "url": ""
    }

    if not opts.ch_open_url_with_js:
        util.printD(f"Open Url: {url}")
        # open url
        webbrowser.open_new_tab(url)
    else:
        util.printD("Send Url to js")
        content["url"] = url
        output = msg_handler.build_py_msg("open_url", content)

    util.printD("End open_model_url")
    return output


def add_trigger_words(msg):
    """
    add trigger words to prompt
    parameter: model_type, search_term, prompt
    return: [new_prompt, new_prompt]
        - new prompt with trigger words, return twice for txt2img and img2img
    """
    util.printD("Start add_trigger_words")

    result = msg_handler.parse_js_msg(msg)
    if not result:
        util.printD("Parsing js ms failed")
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]
    prompt = result["prompt"]

    model_info = civitai.load_model_info_by_search_term(model_type, search_term)
    if not model_info:
        util.printD(f"Failed to get model info for {model_type} {search_term}")
        return [prompt, prompt]

    if "trainedWords" not in model_info.keys():
        util.printD(f"Failed to get trainedWords from info file for {model_type} {search_term}")
        return [prompt, prompt]

    trained_words = model_info.get("trainedWords", [])
    if len(trained_words) == 0:
        util.printD(f"trainedWords from info file for {model_type} {search_term} is empty")
        return [prompt, prompt]

    # guess if trained words are a list of words or list of prompts
    prompt_list = ',' in trained_words[0]

    # if a list of prompts, join with a newline, else a comma and a space
    separator = "\n" if prompt_list else ", "
    trigger_words = separator.join(trained_words)

    new_prompt = f"{prompt} {trigger_words}"

    util.printD(f"trigger_words: {trigger_words}")
    util.printD(f"prompt: {prompt}")
    util.printD(f"new_prompt: {new_prompt}")

    util.printD("End add_trigger_words")

    # add to prompt
    return [new_prompt, new_prompt]


def use_preview_image_prompt(msg):
    """
    use preview image's prompt as prompt
    parameter: model_type, model_name, prompt, neg_prompt
    return: [new_prompt, new_neg_prompt, new_prompt, new_neg_prompt,]
        - return twice for txt2img and img2img
    """
    util.printD("Start use_preview_image_prompt")

    result = msg_handler.parse_js_msg(msg)
    if not result:
        util.printD("Parsing js ms failed")
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]
    prompt = result["prompt"]
    neg_prompt = result["neg_prompt"]


    model_info = civitai.load_model_info_by_search_term(model_type, search_term)
    if not model_info:
        util.printD(f"Failed to get model info for {model_type} {search_term}")
        return [prompt, neg_prompt, prompt, neg_prompt]

    images = model_info.get("images", [])
    if len(images) == 0:
        util.printD(f"No images from info file for {model_type} {search_term}")
        return [prompt, neg_prompt, prompt, neg_prompt]

    # get prompt from preview images' meta data
    preview_prompt = ""
    preview_neg_prompt = ""
    for img in images:
        meta = img.get("meta", {})
        preview_prompt = meta.get("prompt", "")
        preview_neg_prompt = meta.get("negativePrompt", "")

        # we only need 1 prompt
        if preview_prompt:
            break

    if not preview_prompt:
        util.printD(f"There is no prompt of {model_type} {search_term} in its preview image")
        return [prompt, neg_prompt, prompt, neg_prompt]

    util.printD("End use_preview_image_prompt")

    return [preview_prompt, preview_neg_prompt, preview_prompt, preview_neg_prompt]



def dl_model_new_version(msg, max_size_preview, nsfw_preview_threshold):
    """
    download model's new verson by model path, version id and download url
    output is a md log

    This method is triggered by a click event on the client/js
    side that sends a signal to download a single new model
    version. The actual check for new models is in
    `model_action_civitai.check_models_new_version_to_md`.
    return: output:str
    """
    util.printD("Start dl_model_new_version")

    output = ""

    result = msg_handler.parse_js_msg(msg)
    if not result:
        output = "Parsing js msg failed"
        util.printD(output)
        return output

    model_path = result["model_path"]
    version_id = result["version_id"]
    download_url = result["download_url"]
    model_type = result["model_type"]

    # check data
    if not (model_path and version_id and download_url):
        output = util.dedent(f"""
            Missing parameter:
            * model_path: {model_path}
            * version_id: {version_id}
            * download_url: {download_url}
        """)
        util.printD(output)
        return output

    util.printD(f"model_path: {model_path}")
    util.printD(f"version_id: {version_id}")
    util.printD(f"download_url: {download_url}")

    if not os.path.isfile(model_path):
        output = f"model_path is not a file: {model_path}"
        util.printD(output)
        return output

    # get model folder from model path
    model_folder = os.path.dirname(model_path)

    # download file
    success, msg = downloader.dl(download_url, model_folder, None, None)
    if not success:
        return util.download_error(download_url, msg)

    # get version info
    version_info = civitai.get_version_info_by_version_id(version_id)

    # now write version info to files
    model.process_model_info(msg, version_info, model_type)

    # then, get preview image
    civitai.get_preview_image_by_model_path(msg, max_size_preview, nsfw_preview_threshold)

    output = f"Done. Model downloaded to: {msg}"
    util.printD(output)
    return output


def get_model_path_from_js_msg(result):
    """
    Gets a model path based on the webui js_msg.

    return: model_path
    """
    if not result:
        output = "Parsing js ms failed"
        util.error(output)
        util.printD(output)
        return None

    model_type = result["model_type"]
    search_term = result["search_term"]

    model_path = model.get_model_path_by_search_term(model_type, search_term)
    if not model_path:
        output = f"Fail to get model for {model_type} {search_term}"
        util.error(output)
        util.printD(output)
        return None

    if not os.path.isfile(model_path):
        output = f"Model {model_type} {search_term} does not exist, no need to remove"
        util.error(output)
        util.printD(output)
        return None

    return model_path

def make_new_filename(candidate_file, model_name, new_name):
    """
    Substitutes and old model name for a new model name.
    return: new_path:str or None
    """
    path, filename = os.path.split(candidate_file)

    if filename.index(model_name) != 0:
        output = util.dedent(f"""
                Could not find model_name in candidate file
                * Model: {model_name}
                * File:  {candidate_file}
                * Name:  {new_name}
            """
        )
        util.error(output)
        util.printD(output)
        return None

    # handles [model_name].civitai.info and [model_name].preview.[ext]
    new_filename = filename.replace(model_name, new_name, 1)

    new_path = os.path.join(path, new_filename)

    return new_path


def rename_model_by_path(msg):
    """
    Rename a model file and all related ch_helper/
    preview image files.
    """
    util.printD("Start rename_model_by_path")

    output = ""
    result = msg_handler.parse_js_msg(msg)

    model_path = get_model_path_from_js_msg(result)

    if model_path is None:
        output = "Could not rename model."
        return output

    # all files need to be renamed
    model_files = model.get_model_files_from_model_path(model_path)
    model_name = Path(model_path).stem
    new_name = result["new_name"]

    renamed = []
    for candidate_file in model_files:
        new_path = make_new_filename(candidate_file, model_name, new_name)
        if new_path is None:
            continue

        renamed.append(f"* {candidate_file} to {new_path}")
        util.printD(f"Renaming file {candidate_file} to {new_path}")
        os.rename(candidate_file, new_path)

    renamed = "\n".join(renamed)
    output = f"The following files were renamed: \n{renamed}"
    util.info(output)

    util.printD("End rename_model_by_path")
    return output


def remove_model_by_path(msg):
    """
    Remove a model file and all related ch_helper/
    preview image files.
    """
    output = ""
    util.printD("Start remove_model_by_path")

    result = msg_handler.parse_js_msg(msg)

    model_path = get_model_path_from_js_msg(result)

    if model_path is None:
        output = "Could not remove model."
        return output

    # all files need to be renamed
    model_files = model.get_model_files_from_model_path(model_path)

    removed = []
    for candidate_file in model_files:
        util.printD(f"* Removing file {candidate_file}")
        removed.append(candidate_file)
        os.remove(candidate_file)

    removed = "\n".join(removed)
    output = f"The following files were removed: \n{removed}"
    util.info(output)

    util.printD("End remove_model_by_path")
    return output
