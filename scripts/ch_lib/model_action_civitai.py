""" -*- coding: UTF-8 -*-
handle msg between js and python side
"""
import os
import time
import re
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
    return {
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
        "downloadUrl": ""
    }


def scan_single_model(filename, root, model_type, refetch_old, delay):
    """
    Gets model info for a model by feeding its sha256 hash into civitai's api

    return: success:bool
    """

    # check ext
    item = os.path.join(root, filename)
    _, ext = os.path.splitext(item)
    if ext not in model.EXTS:
        return False

    # find a model, get info file
    info_file, sd15_file = model.get_model_info_paths(item)

    # check info file
    if model.metadata_needed(info_file, sd15_file, refetch_old):
        util.printD(f"Creating model info for: {filename}")
        # get model's sha256
        sha256_hash = util.gen_file_sha256(item)

        if not sha256_hash:
            output = f"failed generating SHA256 for model: {filename}"
            util.printD(output)
            return False

        # use this sha256 to get model info from civitai
        model_info = civitai.get_model_info_by_hash(sha256_hash)

        if (model_info == {}) and not model_info.get("id", None):
            model_info = dummy_model_info(item, sha256_hash, model_type)

        model.process_model_info(item, model_info, model_type, refetch_old=refetch_old)

        # delay before next request, to prevent being treated as a DDoS attack
        util.printD(f"delay: {delay} second")
        time.sleep(delay)

    else:
        util.printD(f"Model metadata not needed for {filename}")

    return True


def scan_model(scan_model_types, max_size_preview, nsfw_preview_threshold, refetch_old):
    """ Scan model to generate SHA256, then use this SHA256 to get model info from civitai
        return output msg
    """

    delay = 0.2

    util.printD("Start scan_model")
    output = ""

    # check model types
    if not scan_model_types:
        output = "Model Types is None, can not scan."
        util.printD(output)
        return output

    model_types = []

    # check type if it is a string
    if isinstance(scan_model_types, str):
        model_types.append(scan_model_types)
    else:
        model_types = scan_model_types

    count = 0

    for model_type, model_folder in model.folders.items():
        if model_type not in model_types:
            continue

        util.printD(f"Scanning path: {model_folder}")
        for root, _, files in os.walk(model_folder, followlinks=True):
            for filename in files:
                success = scan_single_model(filename, root, model_type, refetch_old, delay)

                if not success:
                    continue

                # set model_count
                count = count + 1

                # check preview image
                filepath = os.path.join(root, filename)
                civitai.get_preview_image_by_model_path(
                    filepath,
                    max_size_preview,
                    nsfw_preview_threshold
                )

    # this previously had an image count, but it always matched the model count.
    output = f"Done. Scanned {count} models."

    util.printD(output)

    return output


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

    file_metadata = sd_models.read_metadata_from_safetensors(path)

    tag_frequency = file_metadata.get("ss_tag_frequency", {})

    for tag in tag_frequency.keys():
        word = re.sub(r"^\d+_", "", tag)
        trained_words.append(word)

    return model_info


def get_model_info_by_input(
    model_type, model_name, model_url_or_id, max_size_preview, nsfw_preview_threshold
):
    """
    Get model info by model type, name and url
    output is log info to display on markdown component
    """
    output = ""

    # parse model id
    model_id = civitai.get_model_id_from_url(model_url_or_id)
    if not model_id:
        output = f"failed to parse model id from url: {model_url_or_id}"
        util.printD(output)
        return output

    # get model file path
    # model could be in subfolder
    model_path = model.get_model_path_by_type_and_name(model_type, model_name)

    if model_path is None:
        output = "Could not get Model Path"
        util.printD(output)
        return output

    # get model info
    #we call it model_info, but in civitai, it is actually version info
    model_info = civitai.get_version_info_by_model_id(model_id)

    model.process_model_info(model_path, model_info, model_type)

    # check preview image
    civitai.get_preview_image_by_model_path(model_path, max_size_preview, nsfw_preview_threshold)
    return output


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

    count = 0
    if not new_versions:
        util.printD("Done: no new versions found.")
        return "No models have new versions"

    articles = []
    for new_version in new_versions:
        article = build_article_from_version(new_version)
        articles.append(article)

        count = count+1

    output = f"Found new versions for following models: <section>{''.join(articles)}</section>"

    if count != 1:
        util.printD(f"Done. Found {count} models that have new versions. Check UI for detail")
    else:
        util.printD(f"Done. Found {count} model that has a new version. Check UI for detail.")

    return output


def get_model_info_by_url(model_url_or_id:str) -> tuple:
    """
    Retrieves model information necessary to populate HTML
    with Model Name, Model Type, valid saving directories,
    and available model versions.

    return: tuple or None
    """
    util.printD(f"Getting model info by: {model_url_or_id}")

    # parse model id
    model_id = civitai.get_model_id_from_url(model_url_or_id)
    if not model_id:
        util.printD("Could not parse model id from url or id")
        return None

    model_info = civitai.get_model_info_by_id(model_id)
    if model_info is None:
        util.printD("Connection to Civitai API service failed. Wait a while and try again")
        return None

    if not model_info:
        util.printD("Failed to get model info from url or id")
        return None

    # parse model type, model name, subfolder, version from this model info
    # get model type
    civitai_model_type = model_info.get("type", None)
    if civitai_model_type not in civitai.MODEL_TYPES:
        util.printD(f"This model type is not supported: {civitai_model_type}")
        return None

    model_type = civitai.MODEL_TYPES[civitai_model_type]

    # get model type
    model_name = model_info.get("name", None)
    if model_name is None:
        util.printD("model name is Empty")
        model_name = ""

    # get version lists
    model_versions = model_info.get("modelVersions", None)
    if model_versions is None:
        util.printD("modelVersions is Empty")
        return None

    version_strs = []
    for version in model_versions:
        # version name can not be used as id
        # version id is not readable
        # so , we use name_id as version string
        version_str = f'{version["name"]}_{version["id"]}'
        version_strs.append(version_str)

    # get folder by model type
    folder = model.folders[model_type]
    # get subfolders
    subfolders = util.get_subfolders(folder)
    if not subfolders:
        subfolders = []

    # add default root folder
    subfolders.append("/")

    util.indented_print(f"""
        Got following info for downloading:
        {model_name=}
        {model_type=}
        {subfolders=}
        {version_strs=}
    """)

    return (model_info, model_name, model_type, subfolders, version_strs)


def get_ver_info_by_ver_str(version_str:str, model_info:dict) -> dict:
    """
    get version info by version string

    return: version_info:dict
    """

    if not (version_str and model_info):
        output = util.dedent(f"""
            Missing Parameter:
            * model_info: {model_info}
            * version_str: {version_str}
        """)
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
        output = util.dedent(f"""
            Missing Parameter:
            * model_info: {model_info}
            * version_str: {version_str}
        """)
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

    version_id = None
    download_url = None
    if version:
        download_url = version.get("downloadUrl", None)
        version_id = version.get("id", None)

    if None in [version, version_id, download_url]:
        output = util.dedent(f"""
            Invalid Version Information:
            * version: {version}
            * version_id: {version_id}
            * download_url: {download_url}
        """)
        util.printD(output)
        return None

    util.printD(f"Get Download Url: {download_url}")

    return (version_id, download_url)


def download_all(model_folder, version_id, ver_info, duplicate):
    """
    get all download url from files info
    some model versions have multiple files
    """

    download_urls = []

    for file_info in ver_info.get("files", {}):
        download_url = file_info.get("downloadUrl", None)
        if download_url is not None:
            download_urls.append(download_url)

    if len(download_urls) == 0:
        download_url = ver_info.get("downloadUrl", None)
        if download_url is not None:
            download_urls.append()

    # check if this model already exists
    result = civitai.search_local_model_info_by_version_id(model_folder, version_id)
    if result:
        output = "This model version already exists"
        util.printD(output)
        return None

    # download
    for url in download_urls:
        success, msg = downloader.dl(url, model_folder, None, None, duplicate)
        if not success:
            return None

        if url == ver_info["downloadUrl"]:
            return msg

    return None


def download_one(model_folder, ver_info, duplicate):
    """
    only download one file
    get download url
    """

    url = ver_info["downloadUrl"]
    if not url:
        output = "Fail to get download url, check console log for detail"
        util.printD(output)
        return None

    # download
    success, msg = downloader.dl(url, model_folder, None, None, duplicate)
    if not success:
        util.download_error(url, msg)
        return None

    return msg


def dl_model_by_input(
    model_info:dict,
    model_type:str,
    subfolder_str:str,
    version_str:str,
    dl_all_bool:bool,
    max_size_preview:bool,
    nsfw_preview_threshold:bool,
    duplicate:str
) -> str:
    """ download model from civitai by input
        output to markdown log
    """
    if not (model_info and model_type and subfolder_str and version_str):
        output = util.dedent(f"""
            Missing Parameter:
            * model_info: {model_info}
            * model_type: {model_type}
            * subfolder_str: {subfolder_str}
            * version_str: {version_str}
        """)
        util.printD(output)
        return output

    # get model root folder
    if model_type not in model.folders:
        output = f"Unsupported model type: {model_type}"
        util.printD(output)
        return output

    model_root_folder = model.folders[model_type]

    # get subfolder
    subfolder = ""
    if subfolder_str in ["/", "\\"]:
        subfolder = ""
    elif subfolder_str[:1] in ["/", "\\"]:
        subfolder = subfolder_str[1:]
    else:
        subfolder = subfolder_str

    # get model folder for downloading
    model_folder = os.path.join(model_root_folder, subfolder)
    if not os.path.isdir(model_folder):
        output = f"Model folder is not a dir: {model_folder}"
        util.printD(output)
        return output

    # get version info
    ver_info = get_ver_info_by_ver_str(version_str, model_info)
    if not ver_info:
        output = "Failed to get version info, check console log for detail"
        util.printD(output)
        return output

    version_id = ver_info["id"]

    filepath = None
    msg = None

    if dl_all_bool:
        filepath = download_all(model_folder, version_id, ver_info, duplicate)

    else:
        filepath = download_one(model_folder, ver_info, duplicate)

    if filepath is None:
        filepath = msg

    # get version info
    version_info = civitai.get_version_info_by_version_id(version_id)
    model.process_model_info(filepath, version_info, model_type)

    # then, get preview image
    civitai.get_preview_image_by_model_path(filepath, max_size_preview, nsfw_preview_threshold)

    output = f"Done. Model downloaded to: {filepath}"
    util.printD(output)
    return output
