""" -*- coding: UTF-8 -*-
handle msg between js and python side
"""
import os
import time
import re
import gradio as gr
from modules import sd_models
from . import util
from . import model
from . import civitai
from . import downloader
from . import templates


def get_metadata_skeleton():
    """
    Used to generate at least something when model is not on civitai.
    """
    metadata = {
        "id": "",
        "modelId": "",
        "name": "",
        "trainedWords": [],
        "baseModel": "Unknown",
        "description": "",
        "model": {
            "name": "",
            "type": "",
            "nsfw": "",
            "poi": ""
        },
        "files": [
            {
                "name": "",
                "sizeKB": 0,
                "type": "Model",
                "hashes": {
                    "AutoV2": "",
                    "SHA256": ""
                }
            }
        ],
        "tags": [],
        "downloadUrl": "",
        "skeleton_file": True
    }

    return metadata


def scan_single_model(filepath, model_type, refetch_old, delay):
    """
    Gets model info for a model by feeding its sha256 hash into civitai's api

    return: success:bool
    """

    filename = os.path.basename(filepath)

    # find a model, get info file
    info_file, sd15_file = model.get_model_info_paths(filepath)

    output = ""

    # check info file
    if model.metadata_needed(info_file, sd15_file, refetch_old):
        output = f"Creating model info for: {filename}"
        util.printD(output)
        yield output

        # get model's sha256
        result = None
        for result in util.gen_file_sha256(filepath):
            if isinstance(result, tuple):
                yield result

        sha256_hash = result

        util.printD(f"model action sha256: {sha256_hash}")

        if not sha256_hash:
            output = f"failed generating SHA256 for model: {filename}"
            util.printD(output)
            yield output
            time.sleep(delay)
            yield False

        yield "Requesting model information from Civitai"
        # use this sha256 to get model info from civitai
        model_info = civitai.get_model_info_by_hash(sha256_hash)

        if not model_info:
            model_info = dummy_model_info(filepath, sha256_hash, model_type)

        model.process_model_info(filepath, model_info, model_type, refetch_old=refetch_old)

        # delay before next request, to prevent being treated as a DDoS attack
        time.sleep(delay)

    else:
        util.printD(f"Model metadata not needed for {filename}")

    yield True


def scan_model(scan_model_types, nsfw_preview_threshold, refetch_old, progress=gr.Progress()):
    """ Scan model to generate SHA256, then use this SHA256 to get model info from civitai
        return output msg
    """

    delay = 0.2

    util.printD("Start scan_model")
    output = ""

    max_size_preview = util.get_opts("ch_max_size_preview")

    # check model types
    if not scan_model_types:
        output = "Model Types is None, can not scan."
        util.printD(output)
        yield output
        return

    model_types = scan_model_types
    if isinstance(scan_model_types, str):
        # check if type is a string
        model_types = [scan_model_types]

    models = []
    for model_type, model_folder in model.folders.items():
        if model_type not in model_types:
            continue

        util.printD(f"Scanning path: {model_folder}")
        for root, _, files in os.walk(model_folder, followlinks=True):
            for filename in files:

                # check ext
                filepath = os.path.join(root, filename)
                _, ext = os.path.splitext(filepath)
                if ext not in model.EXTS:
                    continue

                models.append((filepath, model_type))

    count = [0, 0]
    total = len(models)
    for filepath, model_type in models:
        success = None

        tracker = (count[0], total)

        progress(
            tracker,
            desc="Scanning...",
            unit="models"
        )

        count[0] = count[0] + 1

        for result in scan_single_model(filepath, model_type, refetch_old, delay):
            if isinstance(result, str):
                progress(tracker, desc=result, unit="models")
                continue

            if isinstance(result, tuple):
                percent, status = result
                progress(percent, desc=status)
                continue

            success = result
            break

        if not success:
            continue

        # set model_count
        count[1] = count[1] + 1

        # check preview image
        for _ in civitai.get_preview_image_by_model_path(
            filepath,
            max_size_preview,
            nsfw_preview_threshold
        ):
            pass

    # this previously had an image count, but it always matched the model count.
    output = f"Done. Successfully scanned {count[1]} of {len(models)} models."

    util.printD(output)

    yield output


def dummy_model_info(path, sha256_hash, model_type):
    """
    Fills model metadata with information we can get locally.
    """
    if not sha256_hash:
        return {}

    model_info = get_metadata_skeleton()

    autov2 = sha256_hash[:10]
    filename = os.path.basename(path)
    filesize = os.path.getsize(path) // 1024

    model_metadata = model_info["model"]
    file_metadata = model_info["files"][0]

    model_metadata["name"] = filename
    model_metadata["type"] = model_type

    file_metadata["name"] = filename
    file_metadata["sizeKB"] = filesize
    file_metadata["hashes"]["SHA256"] = sha256_hash
    file_metadata["hashes"]["AutoV2"] = autov2

    # We can't get data on the model from civitai, but some models
    # do store their training data.
    trained_words = model_info["trainedWords"]
    tags = model_info["tags"]

    try:
        file_metadata = sd_models.read_metadata_from_safetensors(path)
    except AssertionError:
        # model is not a safetensors file. This is fine,
        # it just doesn't have metadata we can read
        pass

    tag_frequency = file_metadata.get("ss_tag_frequency", {})

    for trained_word in tag_frequency.keys():
        # kohya training scripts use
        # `{iterations}_{trained_word}`
        # for training finetune concepts.
        word = re.sub(r"^\d+_", "", trained_word)
        trained_words.append(word)

        # "tags" in this case are just words used in image captions
        # when training the finetune model.
        # They may or may not be useful for prompting
        for tag in tag_frequency[trained_word].keys():
            tag = tag.replace(",", "").strip()
            if tag == "":
                continue
            tags.append(tag)

    return model_info


def get_model_info_by_input(
    model_type, model_name, model_url_or_id, nsfw_preview_threshold
):
    """
    Get model info by model type, name and url
    output is log info to display on markdown component
    """
    output = ""

    max_size_preview = util.get_opts("ch_max_size_preview")

    # parse model id
    model_id = civitai.get_model_id_from_url(model_url_or_id)
    if not model_id:
        output = f"failed to parse model id from url: {model_url_or_id}"
        util.printD(output)
        yield output
        return

    # get model file path
    # model could be in subfolder
    model_path = model.get_model_path_by_type_and_name(model_type, model_name)

    if model_path is None:
        output = "Could not get Model Path"
        util.printD(output)
        yield output
        return

    # get model info
    #we call it model_info, but in civitai, it is actually version info
    model_info = civitai.get_version_info_by_model_id(model_id)

    model.process_model_info(model_path, model_info, model_type)

    # check preview image + webui-visible progress bar
    yield from civitai.get_preview_image_by_model_path(
        model_path,
        max_size_preview,
        nsfw_preview_threshold
    )

    yield output


def build_article_from_version(version):
    """
    Builds the HTML for displaying new model versions to the user.

    return: html:str
    """
    (
        model_path, model_id, model_name, new_version_id,
        new_version_name, description, download_url,
        img_url, model_type
    ) = version

    thumbnail = ""
    if img_url:
        thumbnail = templates.thumbnail.substitute(
            img_url=img_url,
        )

    if download_url:
        # replace "\" to "/" in model_path for windows
        download_model_path = model_path.replace('\\', '\\\\')

        download_section = templates.download.substitute(
            new_version_id=new_version_id,
            new_version_name=new_version_name,
            model_path=download_model_path,
            model_type=model_type,
            download_url=download_url
        )

    else:
        download_section = templates.no_download.substitute(
            new_version_name=new_version_name,
        )

    description_section = ""
    if description:
        description_section = templates.description.substitute(
            description=util.safe_html(download_section),
        )

    article = templates.article.substitute(
        url=f'{civitai.URLS["modelPage"]}{model_id}',
        thumbnail=thumbnail,
        download=download_section,
        description=description_section,
        model_name=model_name,
        model_path=model_path
    )

    return article


def check_models_new_version_to_md(model_types:list) -> str:
    """
    check models' new version and output to UI as html doc
    return: html:str
    """
    new_versions = civitai.check_models_new_version_by_model_types(model_types, 0.2)

    if not new_versions:
        util.printD("Done: no new versions found.")
        return "No models have new versions"

    articles = []
    count = 0
    for index, new_version in enumerate(new_versions):
        article = build_article_from_version(new_version)
        articles.append(article)

    output = f"Found new versions for following models: <section>{''.join(articles)}</section>"

    count = index + 1

    if count != 1:
        util.printD(f"Done. Found {count} models that have new versions. Check UI for detail")
    else:
        util.printD(f"Done. Found {count} model that has a new version. Check UI for detail.")

    return output


def get_model_info_by_id(model_id:str) -> dict:
    """
    Retrieves model information necessary to populate HTML
    with Model Name, Model Type, valid saving directories,
    and available model versions.

    return: tuple or None
    """
    util.printD(f"Getting model info for: {model_id}")

    try:
        # download model info
        model_info = civitai.get_model_info_by_id(model_id)

        # parse model type, model name, subfolder, version from this model info
        # get model type
        civitai_model_type = model_info["type"]

        if civitai_model_type not in civitai.MODEL_TYPES:
            util.printD(f"This model type is not supported: {civitai_model_type}")
            return None

        model_type = civitai.MODEL_TYPES[civitai_model_type]

        # get model type
        model_name = model_info["name"]

        # get version lists
        model_versions = model_info["modelVersions"]

    except (KeyError, ValueError, TypeError) as e:
        util.printD(f"An error occurred while attempting to process model info: \n\t{e}")
        return None

    filenames = []
    files = []
    version_strs = []
    previews = {}
    for version in model_versions:
        # version name can not be used as id
        # version id is not readable
        # so , we use name_id as version string
        version_str = f'{version["name"]}_{version["id"]}'

        filename = ""
        try:
            for filedata in version["files"]:
                if filedata["type"] == "Model":
                    filename = filedata["name"]

        except (ValueError, KeyError):
            pass

        files.append(version["files"])
        filenames.append(filename)
        version_strs.append(version_str)
        previews[version_str] = version["images"]

    # get folder by model type
    folder = model.folders[model_type]

    # get subfolders
    subfolders = ["/"] + util.get_subfolders(folder)

    msg = util.indented_msg(f"""
        Got following info for downloading:
        {model_name=}
        {model_type=}
        {version_strs=}
        {subfolders=}
        {previews=}
    """)
    util.printD(msg)

    return {
        "model_info": model_info,
        "model_name": model_name,
        "model_type": model_type,
        "files": files,
        "filenames": filenames,
        "subfolders": subfolders,
        "version_strs": version_strs,
        "previews": previews
    }


def get_ver_info_by_ver_str(version_str:str, model_info:dict) -> dict:
    """
    get version info by version string

    return: version_info:dict
    """

    if not (version_str and model_info):
        output = util.indented_msg(
            f"""
            Missing Parameter:
            {model_info=}
             {version_str=}
            """
            )
        util.printD(output)
        return None

    # get version list
    model_versions = model_info.get("modelVersions", None)
    if model_versions is None:
        util.printD("modelVersions is Empty")
        return None

    # find version by version_str
    version = None
    for ver in model_versions:
        # version name can not be used as id
        # version id is not readable
        # so , we use name_id as version string
        ver_str = f'{ver["name"]}_{ver["id"]}'
        if ver_str == version_str:
            # find version
            version = ver
            break

    if not (version and ("id" in version)):
        util.printD(f"can not find version or id by version string: {version_str}")
        return None

    return version


def get_id_and_dl_url_by_version_str(version_str:str, model_info:dict) -> tuple:
    """
    get download url from model info by version string
    return - (version_id, download_url)
    """
    if not (version_str and model_info):
        output = util.indented_msg(f"""
            Missing Parameter:
            {model_info=}
            {version_str=}
        """)
        util.printD(output)
        return (False, output)

    # get version list
    model_versions = model_info.get("modelVersions", None)
    if model_versions is None:
        util.printD("modelVersions is Empty")
        return (False, output)

    # find version by version_str
    version = None
    for ver in model_versions:
        # version name can not be used as id
        # version id is not readable
        # so , we use name_id as version string
        ver_str = f'{ver["name"]}_{ver["id"]}'
        if ver_str == version_str:
            # find version
            version = ver
            break

    version_id = None
    download_url = None
    if version:
        download_url = version.get("downloadUrl", None)
        version_id = version.get("id", None)

    if None in [version, version_id, download_url]:
        output = util.indented_msg(f"""
            Invalid Version Information:
            {version=}
            {version_id=}
            {download_url=}
        """)
        util.printD(output)
        return (False, output)

    util.printD(f"Get Download Url: {download_url}")

    return (version_id, download_url)

def parse_file_info(file_info, basename):
    """
        returns data required to download a file from civitai
    """

    download_url = file_info.get("downloadUrl", None)
    if download_url is None:
        return None

    filetype = file_info["type"]
    filename = file_info["name"]
    if basename and not filetype == "VAE":
        filename = f"{basename}.{filename.split('.')[-1]}"

    return {
        "url": download_url,
        "filename": filename,
        "type": filetype
    }


def download_files(filename, model_folder, ver_info, headers, filetypes, dl_all, duplicate):
    """
    get download urls from files info
    some model versions have multiple files
    """

    version_id = ver_info["id"]
    model_id = ver_info["model_id"]

    model_ids = {
        "model": model_id,
        "version": version_id
    }

    downloads = []

    # check if this model already exists
    result = civitai.search_local_model_info_by_version_id(model_folder, model_ids)
    if result:
        output = f"This model version already exists at `{result}`"
        util.printD(output)
        yield (False, output)

    for file_info in ver_info.get("files", {}):
        if not dl_all:
            if not file_info["type"] in filetypes:
                continue

        dl_info = parse_file_info(file_info, filename)

        if dl_info:
            downloads.append(dl_info)

    if len(downloads) == 0:
        dl_info = parse_file_info(ver_info, filename)
        if dl_info:
            downloads.append(dl_info)

    # download
    success = False
    output = ""
    filepath = None
    total = len(downloads)
    errors = []
    errors_count = 0
    snippet = None

    for index, dl_info in enumerate(downloads):

        url = dl_info["url"]
        if errors_count > 0:
            snippet = f"{errors_count}/{total} files failed"

        dl_folder = model_folder
        if dl_info["type"] == "VAE":
            dl_folder = model.vae_folder

        # webui visible progress bar
        for result in downloader.dl_file(
            url, filename=dl_info["filename"], folder=dl_folder, duplicate=duplicate,
            headers=headers
        ):
            if not isinstance(result, str):
                success, output = result
                break

            output = f"{result} | {index+1}/{total} files"
            if snippet:
                " | ".join([output, snippet])

            yield output

        if not success:
            errors.append(downloader.error(url, output))
            errors_count += 1
            continue

        if dl_info["type"] == "Model":
            filepath = output

    additional = None
    if errors_count > 0:
        additional = "\n\t".join(errors)

        if errors_count == total:
            yield (False, additional)
            return

    yield (True, filepath, additional)


def download_one(filename, model_folder, ver_info, headers, duplicate):
    """
    only download one file
    get download url
    """

    download_url = ver_info["downloadUrl"]

    output = ""
    if not download_url:
        output = "Failed to find a download url"
        util.printD(output)
        yield (False, output)

    # download
    success = False
    for result in downloader.dl_file(
        download_url, filename=filename, folder=model_folder,
        duplicate=duplicate, headers=headers
    ):
        if not isinstance(result, str):
            success, output = result
            break

        yield result

    if not success:
        downloader.error(download_url, output)
        yield (False, output)

    yield (True, output)


def dl_model_by_input(
    ch_state:dict,
    model_type:str,
    subfolder_str:str,
    version_str:str,
    filename:str,
    file_ext:str,
    dl_all:bool,
    nsfw_preview_threshold:int,
    duplicate:str,
    preview:str,
    *args
) -> str:
    """ download model from civitai by input
        output to markdown log
    """

    model_info = ch_state["model_info"]
    max_size_preview = util.get_opts("ch_max_size_preview")

    if not (model_info and model_type and subfolder_str and version_str):
        output = util.indented_msg(f"""
            Missing Required Parameter in dl_model_by_input. Parameters given:
            {model_type=}*
            {subfolder_str=}*
            {version_str=}*
            {filename=}
            {file_ext=}
            {max_size_preview=}
            {nsfw_preview_threshold=}
            {duplicate=}
        """)

        # Keep model info away from util.indented_msg
        # which can screw with complex strings
        output = f"{output}\n    {model_info=}*\n    * Required"
        util.printD(output)
        yield output
        return

    # get model root folder
    if model_type not in model.folders:
        output = f"Unsupported model type: {model_type}"
        util.printD(output)
        yield output
        return

    folder = ""
    subfolder = ""
    output = ""
    version_info = None

    filetypes = []
    for filetype, will_dl in zip(civitai.FILE_TYPES, args):
        if will_dl:
            filetypes.append(filetype)

    model_root_folder = model.folders[model_type]

    if not os.path.exists(model_root_folder):
        # Model directories may not exist by default
        os.mkdir(model_root_folder)

    # get subfolder
    if subfolder_str in ["/", "\\"]:
        subfolder = ""
    elif subfolder_str[:1] in ["/", "\\"]:
        subfolder = subfolder_str[1:]
    else:
        subfolder = subfolder_str

    # get model folder for downloading
    folder = os.path.join(model_root_folder, subfolder)
    if not os.path.isdir(folder):
        output = f"Model folder is not a dir: {folder}"
        util.printD(output)
        yield output
        return

    # get version info
    ver_info = get_ver_info_by_ver_str(version_str, model_info)
    ver_info["model_id"] = model_info["id"]
    if not ver_info:
        output = "Failed to get version info, check console log for detail"
        util.printD(output)
        yield output
        return

    headers = {
        "content-type": "application/json"
    }
    api_key = util.get_opts("ch_civiai_api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    additional = None
    for result in download_files(filename, folder, ver_info, headers, filetypes, dl_all, duplicate):
        if not isinstance(result, str):
            if len(result) > 2:
                success, output, additional = result
            else:
                success, output = result

            break

        yield result

    if not success:
        yield output
        return

    # get version info
    version_info = civitai.get_version_info_by_version_id(ver_info["id"])
    model.process_model_info(output, version_info, model_type)

    # then, get preview image + webui-visible progress
    for result in civitai.get_preview_image_by_model_path(
        output,
        max_size_preview,
        nsfw_preview_threshold,
        preferred_preview=preview
    ):
        yield f"Downloading model preview:\n{result}"

    output = f"Done. Downloaded to: {output}"
    if additional:
        output = f"{output}. Additionally, the following failures occurred: \n{additional}"
    util.printD(output)
    yield output
