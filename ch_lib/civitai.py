""" -*- coding: UTF-8 -*-
handle msg between js and python side
"""

import os
import re
from . import util
from . import model
from . import downloader

SUFFIX = ".civitai"

URLS = {
    "query": "https://civitai.com/api/v1/models?",
    "modelPage": "https://civitai.com/models/",
    "modelId": "https://civitai.com/api/v1/models/",
    "modelVersionId": "https://civitai.com/api/v1/model-versions/",
    "hash": "https://civitai.com/api/v1/model-versions/by-hash/"
}

MODEL_TYPES = {
    "Checkpoint": "ckp",
    "TextualInversion": "ti",
    "Hypernetwork": "hyper",
    "LORA": "lora",
    "LoCon": "lycoris",
    "DoRA": "lora"
}

MODEL_CATEGORIES = {
    "character",
    "style",
    "celebrity",
    "concept",
    "clothing",
    "base model",
    "poses",
    "background",
    "tool",
    "buildings",
    "vehicle",
    "objects",
    "animal",
    "action",
    "assets"
}

FILE_TYPES = [
    "Model", "Training Data", "Config", "VAE"
]

# https://github.com/civitai/civitai/blob/a7b9fbfadc0e463b568be015c381e2452e32b210/src/server/common/enums.ts#L196-L203
NSFW_LEVELS = {
    "PG": 1,
    "PG13": 2,
    "R": 4,
    "X": 8,
    "XXX": 16
    # Probably not actually visible through the API without being logged in on model owner account?
    # "Blocked": 32,
}


def civitai_get(civitai_url: str):
    """
    Gets JSON from Civitai.
    return: dict:json or None
    """

    util.printD(f"Requesting Civitai: {civitai_url}")

    success, response = downloader.request_get(
        civitai_url
    )

    if not success:
        return None

    # try to get content
    content = None
    try:
        content = response.json()
    except ValueError as e:
        util.printD(util.indented_msg(
            f"""
            Parse response json failed
            Error: {str(e)}
            Response: {response.text}
            """
        ))
        return None

    return content


def append_parent_model_metadata(content):
    """
    Some model metadata is stored in a "parent" context.
    When we're fething a model by its hash, we're getting
    the metadata for that model *file*, not the model entry
    on Civitai, which may contain multiple versions.

    This method gets the parent metadata and appends it to
    our model file metadata.

    return: model metadata with parent description, creator,
    and permissions appended.
    """
    util.printD("Fetching Parent Model Information")
    parent_model = get_model_info_by_id(content["modelId"])

    if not parent_model:
        # Archived models can give the model version information but 404 on the model metadata itself.
        parent_model = {}

    metadatas = [
        "description", "tags", "allowNoCredit",
        "allowCommercialUse", "allowDerivatives",
        "allowDifferentLicense"
    ]

    content["creator"] = parent_model.get("creator", "{}")

    model_metadata = content["model"]
    for metadata in metadatas:
        model_metadata[metadata] = parent_model.get(metadata, "")

    return content


def get_model_info_by_hash(model_hash: str):
    """
    use this sha256 to get model info from civitai's api

    return:
        model info dict if a model is found
        {} if civitai does not have the model
        None if an error occurs.
    """
    util.printD("Request model info from civitai")

    if not model_hash:
        util.printD("hash is empty")
        return None

    try:
        content = civitai_get(f'{URLS["hash"]}{model_hash}')
    except Exception as e:
        util.printD(f"Failed to get model info by hash: {model_hash}")
        util.printD(f"Error: {str(e)}")
        return None

    if not content:
        return None

    #util.printD(content)

    content = append_parent_model_metadata(content)

    return content


def get_model_info_by_id(model_id: str) -> dict:
    """
    Fetches model info by its model id.
    returns: dict:model_info
    """

    util.printD(f"Request model info from civitai: {model_id}")

    if not model_id:
        util.printD("model_id is empty")
        return False

    content = civitai_get(f'{URLS["modelId"]}{model_id}')

    return content


def get_version_info_by_version_id(version_id: str) -> dict:
    """
    Gets model version info from Civitai by version id
    return: dict:model_info
    """
    util.printD("Request version info from civitai")

    if not version_id:
        util.printD("version_id is empty")
        return None

    content = civitai_get(f'{URLS["modelVersionId"]}{version_id}')

    if content:
        content = append_parent_model_metadata(content)

    return content


def get_version_info_by_model_id(model_id: str) -> dict:
    """
    Fetches version info by model id.
    returns: dict:version_info
    """

    model_info = get_model_info_by_id(model_id)
    if not model_info:
        util.printD(f"Failed to get model info by id: {model_id}")
        return None

    # check content to get version id
    versions = model_info.get("modelVersions", [])
    if len(versions) == 0:
        util.printD("Found no model versions")
        return None

    def_version = versions[0]
    if not def_version:
        util.printD("default version is None")
        return None

    version_id = def_version.get("id", "")

    if not version_id:
        util.printD("Could not get valid version id")
        return None

    # get version info
    version_info = get_version_info_by_version_id(f"{version_id}")
    if not version_info:
        util.printD(f"Failed to get version info by version_id: {version_id}")
        return None

    return version_info


def load_model_info_by_search_term(model_type, search_term):
    """
    get model info file's content by model type and search_term
    parameter: model_type, search_term
    return: model_info
    """
    util.printD(f"Load model info of {search_term} in {model_type}")
    if model.folders.get(model_type, None) is None:
        util.printD(f"unknown model type: {model_type}")
        return None

    # search_term = f"{subfolderpath}{model name}{ext}"
    # And it always start with a / even when there is no sub folder
    base, _ = os.path.splitext(search_term)
    model_info_base = base
    if base[:1] == "/":
        model_info_base = base[1:]

    if model_type == "lora" and model.folders['lycoris']:
        model_folders = [model.folders[model_type], model.folders['lycoris']]
    else:
        model_folders = [model.folders[model_type]]

    for model_folder in model_folders:
        model_info_filename = f"{model_info_base}{SUFFIX}{model.CIVITAI_EXT}"
        model_info_filepath = os.path.join(model_folder, model_info_filename)

        found = os.path.isfile(model_info_filepath)

        if found:
            break

    if not found:
        util.printD(f"Can not find model info file: {model_info_filepath}")
        return None

    return model.load_model_info(model_info_filepath)


def get_model_names_by_type_and_filter(model_type: str, metadata_filter: dict) -> list:
    """
    get model file names by model type
    parameter: model_type - string
    parameter: filter - dict, which kind of model you need
    return: model name list
    """

    if model_type == "lora" and model.folders['lycoris']:
        model_folders = [model.folders[model_type], model.folders['lycoris']]
    else:
        model_folders = [model.folders[model_type]]

    # set metadata_filter
    # only get models don't have a civitai info file
    no_info_only = False
    empty_info_only = False

    if metadata_filter:
        no_info_only = metadata_filter.get("no_info_only", False)
        empty_info_only = metadata_filter.get("empty_info_only", False)

    # get information from filter
    # only get those model names don't have a civitai model info file
    model_names = []
    for model_folder in model_folders:
        for root, _, files in os.walk(model_folder, followlinks=True):
            for filename in files:
                if is_valid_file(root, filename, no_info_only, empty_info_only):
                    model_names.append(filename)

    return model_names


def is_valid_file(root, filename, no_info_only, empty_info_only):
    """
    Filters through model files to determine if they are
    valid targets for downloading new metadata.

    return: bool
    """
    item = os.path.join(root, filename)
    # check extension
    base, ext = os.path.splitext(item)
    if ext not in model.EXTS:
        return False

    # find a model
    info_file = f"{base}{SUFFIX}{model.CIVITAI_EXT}"

    # check filter
    if os.path.isfile(info_file):
        if no_info_only:
            return False

        if empty_info_only:
            # load model info
            model_info = model.load_model_info(info_file)
            # check content
            if model_info and not model_info.get("id", "") == "":
                # find a non-empty model info file
                return False

    return True


def get_model_names_by_input(model_type, empty_info_only):
    """ return: list of model filenames with empty civitai info files """
    return get_model_names_by_type_and_filter(model_type, {"empty_info_only": empty_info_only})


# get id from url
def get_model_id_from_url(url: str, include_model_ver=False) -> str:
    """ return: model_id from civitai url """
    util.printD("Run get_model_id_from_url")
    model_id = None
    model_version_id = None

    if not url:
        util.printD("url or model id can not be empty")
        return None

    if url.isnumeric():
        # is already an model_id
        return url

    model_m = re.search(r"/models/(\d+)", url)
    ver_m = re.search(r"modelVersionId=(\d+)", url)

    try:
        if model_m.group(1):
            model_id = model_m.group(1)
    except AttributeError:
        util.printD("There is no model id in this url")
        return None

    try:
        if ver_m.group(1):
            model_version_id = ver_m.group(1)
    except AttributeError:
        pass

    if not include_model_ver:
        return model_id

    return (model_id, model_version_id)


def preview_exists(model_path):
    """ Search for existing preview image. return True if it exists, else false """

    previews = model.get_potential_model_preview_files(model_path)

    for prev in previews:
        if os.path.isfile(prev):
            return True

    return False


def get_image_url(img_dict, max_size_preview):
    """
    Create the image download URL

    return: url:str
    """

    url = img_dict["url"]
    if max_size_preview:
        # use max width
        width = img_dict.get("width", False)
        if width:
            url = re.sub(r'/width=\d+/', '/width=' + str(width) + '/', url)

    return url


def verify_preview(path, img_dict, max_size_preview, nsfw_preview_threshold):
    """
    Downloads a preview image if it meets the user's requirements.
    """

    img_url = img_dict.get("url", None)
    if img_url is None:
        yield (False, None)

    image_rating = img_dict.get("nsfwLevel", 32)
    if image_rating > 1:
        util.printD(f"This image is NSFW: {image_rating}")
        if NSFW_LEVELS[nsfw_preview_threshold] < image_rating:
            util.printD("Skip NSFW image")
            yield (False, None)

    preview_type = img_dict.get("type")
    if preview_type != "image":
        util.printD(f"Preview is not an image. Found {preview_type} instead. Skipping.")
        yield (False, None)

    img_url = get_image_url(img_dict, max_size_preview)

    success = False
    preview_path = ""
    for result in downloader.dl_file(img_url, file_path=path):
        if not isinstance(result, str):
            success, preview_path = result
            break

        yield result

    if not success:
        yield (False, None)

    # we only need 1 preview image
    yield (True, preview_path)


# get preview image by model path
# image will be saved to file, so no return
def get_preview_image_by_model_path(model_path: str, max_size_preview, nsfw_preview_threshold, preferred_preview=None):
    """
    Downloads a preview image for a model if one doesn't already exist.
    Skips images that are more NSFW than the user's NSFW threshold
    """
    util.printD("Downloading model image.")

    if not model_path:
        util.printD("model_path is empty")
        return

    if not os.path.isfile(model_path):
        util.printD(f"model_path is not a file: {model_path}")
        return

    base, _ = os.path.splitext(model_path)
    preview_path = f"{base}.preview.png"  # TODO png not strictly required
    info_file = f"{base}{SUFFIX}{model.CIVITAI_EXT}"

    # need to download preview image
    util.printD(f"Checking preview image for model: {model_path}")

    if preview_exists(model_path):
        output = "Existing model image found. Skipping."
        util.printD(output)
        yield output
        return

    # load model_info file
    if not os.path.isfile(info_file):
        return

    try:
        images = model.load_model_info(info_file)["images"]

    except (KeyError, TypeError):
        return

    if preferred_preview:
        img_url = preferred_preview
        for img_dict in images:
            if img_dict["url"] == preferred_preview:
                img_url = get_image_url(img_dict, max_size_preview)
                break

        for result in downloader.dl_file(img_url, file_path=preview_path):
            if isinstance(result, str):
                yield result
                continue

            success, msg = result

            if success:
                return

            util.printD(msg)
            util.printD("Failed to download preferred preview. Trying to find another")

            break

    for img_dict in images:
        for result in verify_preview(
                preview_path, img_dict, max_size_preview, nsfw_preview_threshold
        ):
            if not isinstance(result, str):
                success, _ = result
                # Only download one image
                if success:
                    return

                break

            yield result

    util.printD(f"Could not find any valid preview images for model: {model_path}")
    yield


# search local model by version id in 1 folder, no subfolder
# return - model_info
def search_local_model_info_by_version_id(folder: str, model_ids: dict) -> dict:
    """ Searches a folder for model_info files,
        returns the model_info from a file if its id matches the model id.
    """
    util.printD("Searching local model by version id")
    util.printD(f"folder: {folder}")
    util.printD(f"model_ids: {model_ids}")

    version_id = model_ids["version"]
    model_id = model_ids["model"]

    if not folder:
        util.printD("folder is none")
        return None

    if not os.path.isdir(folder):
        util.printD("folder is not a dir")
        return None

    if not (version_id and model_id):
        util.printD("missing ID for model/version")
        return None

    # search civitai model info file
    for filename in os.listdir(folder):
        # check ext
        base, ext = os.path.splitext(filename)
        if ext == model.CIVITAI_EXT:
            # find info file
            if not (len(base) > 8 and base[-8:] == SUFFIX):
                # not a civitai info file
                continue

            # find a civitai info file
            path = os.path.join(folder, filename)

            try:
                model_info = model.load_model_info(path)
                existing_version_id = model_info.get("id", None)
                existing_model_id = model_info["modelId"]

            except Exception:
                continue

            # util.printD(f"Compare version id, src: {model_id}, target:{version_id}")
            if f"{existing_version_id}" == f"{version_id}":
                # find the one
                filepath = model.locate_model_from_partial(folder, base[:-8])
                return f"{filepath}"

    return None


def get_model_id_from_model_path(model_path: str):
    """ return model_id using model_path """
    # get model info file name
    base, _ = os.path.splitext(model_path)
    info_file = f"{base}{SUFFIX}{model.CIVITAI_EXT}"

    if not os.path.isfile(info_file):
        return None

    # get model info
    model_info_file = model.load_model_info(info_file)
    local_version_id = model_info_file.get("id", None)
    model_id = model_info_file.get("modelId", None)

    if None in [model_id, local_version_id]:
        return None

    return (model_id, local_version_id)


def check_model_new_version_by_path(model_path: str, delay: float = 0.2) -> tuple:
    """
    check new version for a model by model path
    return (
        model_path, model_id, model_name, new_verion_id,
        new_version_name, description, download_url, img_url
    )
    """

    if not (model_path and os.path.isfile(model_path)):
        util.printD(f"model_path is not a file: {model_path}")
        return None

    result = get_model_id_from_model_path(model_path)
    if not result:
        return None

    model_id, local_version_id = result

    # get model info by id from civitai
    model_info = get_model_info_by_id(model_id)

    util.delay(delay)

    if not model_info:
        return None

    model_versions = model_info.get("modelVersions", [])

    if len(model_versions) == 0:
        return None

    current_version = model_versions[0]
    if not current_version:
        return None

    current_version_id = current_version.get("id", False)

    util.printD(f"Compare version id, local: {local_version_id}, remote: {current_version_id}")

    if not (current_version_id and current_version_id != local_version_id):
        return None

    model_name = model_info.get("name", "")
    new_version_name = current_version.get("name", "")
    description = current_version.get("description", "")
    download_url = current_version.get("downloadUrl", "")

    # get 1 preview image
    try:
        img_url = current_version["images"][0]["url"]
    except (IndexError, KeyError):
        img_url = ""

    return (
        model_path, model_id, model_name, current_version_id,
        new_version_name, description, download_url, img_url
    )


def check_single_model_new_version(root, filename, model_type, delay):
    """
    return: True if a valid model has a new version.
    """
    # check ext
    item = os.path.join(root, filename)
    _, ext = os.path.splitext(item)

    if ext not in model.EXTS:
        return False

    # find a model
    request = check_model_new_version_by_path(item, delay)

    if not request:
        return False

    request = request + (model_type,)

    # model_path, model_id, model_name, version_id, new_version_name, description, downloadUrl, img_url = request
    model_ids = {
        'model': request[1],
        'version': request[3],
    }

    # check exist
    if not (model_ids['version'] and model_ids['model']):
        return False

    # search this new version id to check if this model is already downloaded
    target_model_info = search_local_model_info_by_version_id(root, model_ids)
    if target_model_info:
        util.printD("New version already exists")
        return False

    return request


def check_models_new_version_by_model_types(model_types: list, delay: float = 0.2) -> list:
    """
    check all models of model_types for new version
    parameter: delay - float, how many seconds to delay between each request to civitai
    return: new_versions
        a list for all new versions, each one is
        (model_path, model_id, model_name, new_verion_id,
        new_version_name, description, download_url, img_url)
    """
    util.printD("Checking models' new version")

    if not model_types:
        return []

    # check model types, which could be a string as 1 type
    mts = []
    if isinstance(model_types, str):
        mts.append(model_types)
    elif isinstance(model_types, list):
        mts = model_types
    else:
        util.printD("Unknown model types:")
        util.printD(model_types)
        return []

    # new version list
    new_versions = []
    new_version_ids = []

    # walk all models
    for model_type, model_folder in model.folders.items():
        if model_type not in mts:
            continue

        util.printD(f"Scanning path: {model_folder}")
        for root, _, files in os.walk(model_folder, followlinks=True):
            for filename in files:
                version = check_single_model_new_version(root, filename, model_type, delay)

                if not version:
                    continue

                # model_path, model_id, model_name, version_id, new_version_name, description, downloadUrl, img_url = version
                version_id = version[3]

                if version_id in new_version_ids:
                    continue

                # add to list
                new_versions.append(version)
                new_version_ids.append(version_id)

    return new_versions


def move_model_to_subfolder(filepath, model_info):
    model_id = model_info["modelId"]

    if model_id == "":
        return None

    content = civitai_get(f'{URLS["modelId"]}{model_id}')

    tags = content["tags"]

    # iterate through tags until we find one that matches MODEL_CATEGORIES

    for tag in tags:
        if tag in MODEL_CATEGORIES:
            model_category = tag

            # create subfolder if it doesn't exist
            # check to make sure the model is not already in the correct subfolder
            if model_category in filepath:
                return filepath

            # get the file path without the filename
            folderpath = os.path.dirname(filepath)

            # create the new folder path
            new_folderpath = os.path.join(folderpath, model_category)

            # create the new folder if it doesn't exist
            if not os.path.isdir(new_folderpath):
                os.makedirs(new_folderpath)

            util.printD(f"Moving model from {filepath} to {new_folderpath}")

            # move the file to the new folder
            new_filepath = os.path.join(new_folderpath, os.path.basename(filepath))
            os.rename(filepath, new_filepath)

            return new_filepath

    util.printD("WARNING: Unable to find tag for folder")

    return filepath
