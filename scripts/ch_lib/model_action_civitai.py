# -*- coding: UTF-8 -*-
# handle msg between js and python side
import os
import time
import re
from . import util
from . import model
from . import civitai
from . import downloader


def get_metadata_skeleton():
    # Used to generate at least something when model is not on civitai.
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



def scan_model(scan_model_types, max_size_preview, skip_nsfw_preview, refetch_old):
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
    if type(scan_model_types) == str:
        model_types.append(scan_model_types)
    else:
        model_types = scan_model_types

    model_count = 0
    image_count = 0

    for model_type, model_folder in model.folders.items():
        if model_type not in model_types:
            continue

        util.printD(f"Scanning path: {model_folder}")
        for root, dirs, files in os.walk(model_folder, followlinks=True):
            for filename in files:
                # check ext
                item = os.path.join(root, filename)
                base, ext = os.path.splitext(item)
                if ext in model.exts:

                    # find a model, get info file
                    info_file, sd15_file = model.get_model_info_paths(item)

                    # check info file
                    if model.metadata_needed(info_file, sd15_file, refetch_old):
                        util.printD(f"Creating model info for: {filename}")
                        # get model's sha256
                        hash = util.gen_file_sha256(item)

                        if not hash:
                            output = f"failed generating SHA256 for model: {filename}"
                            util.printD(output)
                            return output

                        # use this sha256 to get model info from civitai
                        model_info = civitai.get_model_info_by_hash(hash)

                        if (model_info == {}) and not model_info.get("id", None):
                            model_info = dummy_model_info(item, hash, model_type)

                        model.process_model_info(item, model_info, model_type, refetch_old=refetch_old)

                        # delay before next request, to prevent to be treat as DDoS
                        util.printD(f"delay: {delay} second")
                        time.sleep(delay)

                    else:
                        util.printD(f"Model metadata not needed for {filename}")


                    # set model_count
                    model_count = model_count+1

                    # check preview image
                    civitai.get_preview_image_by_model_path(item, max_size_preview, skip_nsfw_preview)
                    image_count = image_count+1

    output = f"Done. Scanned {model_count} models, checked {image_count} images."

    util.printD(output)

    return output


def dummy_model_info(file, hash, model_type):
    if not hash:
        return {}

    model_info = get_metadata_skeleton()

    autov2 = hash[:10]
    filename = os.path.basename(file)
    filesize = int(os.path.getsize(file) / 1024)

    model_metadata = model_info["model"]
    file_metadata = model_info["files"][0]

    model_metadata["name"] = filename
    model_metadata["type"] = model_type

    file_metadata["sizeKB"] = filesize
    file_metadata["hashes"]["SHA256"] = hash
    file_metadata["hashes"]["AutoV2"] = autov2

    return model_info


# Get model info by model type, name and url
# output is log info to display on markdown component
def get_model_info_by_input(model_type, model_name, model_url_or_id, max_size_preview, skip_nsfw_preview):
    output = ""
    # parse model id
    model_id = civitai.get_model_id_from_url(model_url_or_id)
    if not model_id:
        output = f"failed to parse model id from url: {model_url_or_id}"
        util.printD(output)
        return output

    # get model file path
    # model could be in subfolder
    result = model.get_model_path_by_type_and_name(model_type, model_name)
    if not result:
        output = "failed to get model file path"
        util.printD(output)
        return output

    model_root, model_path = result
    if not model_path:
        output = "model path is empty"
        util.printD(output)
        return output

    # get model info
    #we call it model_info, but in civitai, it is actually version info
    model_info = civitai.get_version_info_by_model_id(model_id)

    model.process_model_info(model_path, model_info, model_type)

    # check preview image
    civitai.get_preview_image_by_model_path(model_path, max_size_preview, skip_nsfw_preview)
    return output



# check models' new version and output to UI as markdown doc
def check_models_new_version_to_md(model_types:list) -> str:
    new_versions = civitai.check_models_new_version_by_model_types(model_types, 0.2)

    count = 0
    if not new_versions:
        util.printD("Done: no new versions found.")
        return "No models have new versions"

    output = ["Found new version for following models: <section>"]
    for new_version in new_versions:
        count = count+1
        model_path, model_id, model_name, new_verion_id, new_version_name, description, download_url, img_url, model_type = new_version
        # in md, each part is something like this:
        # [model_name](model_url)
        # [version_name](download_url)
        # version description
        url = f'{civitai.url_dict["modelPage"]}{model_id}'

        output.append('<article style="margin: 5px; clear: both;">')

        # preview image
        if img_url:
            output.append(f"<img src='{img_url}' style='float: left; margin: 5px;'>")

        output.append(f'<div style="font-size:20px;margin:6px 0px;"><b>Model: <a href="{url}" target="_blank"><u>{model_name}</u></a></b></div>')
        output.append(f'<div style="font-size:16px">File: {model_path}</div>')
        if download_url:
            # replace "\" to "/" in model_path for windows
            model_path = model_path.replace('\\', '\\\\')
            output.append(f'<div style="font-size:16px;margin:6px 0px;">New Version: <u><a href="{download_url}" target="_blank" style="margin:0px 10px;">{new_version_name}</a></u>')
            output.append("    ")
            # add js function to download new version into SD webui by python
            # in embed HTML, onclick= will also follow a ", never a ', so have to write it as following
            output.append(f"""<u><a href='#' style='margin:0px 10px;' onclick="ch_dl_model_new_version(event, '{model_path}', '{new_verion_id}', '{download_url}', '{model_type}')">[Download into SD]</a></u>""")

        else:
            output.append(f'<div style="font-size:16px;margin:6px 0px;">New Version: {new_version_name}')

        output.append('</div>')

        if description:
            description = util.safe_html(description)
            output.append(f'<blockquote style="font-size:16px;margin:6px 0px;">{description}</blockquote><br>')

        output.append('</article>')

    output.append('</section>')
    output = "".join(output)

    util.printD(f"Done. Found {count} model{'s' if count != 1 else ''} that {'have' if count != 1 else 'has a'} new version{'s' if count != 1 else ''}. Check UI for detail.")

    return output


# get model info by url
def get_model_info_by_url(model_url_or_id:str) -> tuple:
    util.printD(f"Getting model info by: {model_url_or_id}")

    # parse model id
    model_id = civitai.get_model_id_from_url(model_url_or_id)
    if not model_id:
        util.printD("failed to parse model id from url or id")
        return

    model_info = civitai.get_model_info_by_id(model_id)
    if model_info is None:
        util.printD("Connect to Civitai API service failed. Wait a while and try again")
        return

    if not model_info:
        util.printD("failed to get model info from url or id")
        return

    # parse model type, model name, subfolder, version from this model info
    # get model type
    if "type" not in model_info.keys():
        util.printD("model type is not in model_info")
        return

    civitai_model_type = model_info["type"]
    if civitai_model_type not in civitai.model_type_dict.keys():
        util.printD(f"This model type is not supported: {civitai_model_type}")
        return

    model_type = civitai.model_type_dict[civitai_model_type]

    # get model type
    if "name" not in model_info.keys():
        util.printD("model name is not in model_info")
        return

    model_name = model_info["name"]
    if not model_name:
        util.printD("model name is Empty")
        model_name = ""

    # get version list
    if "modelVersions" not in model_info.keys():
        util.printD("modelVersions is not in model_info")
        return

    modelVersions = model_info["modelVersions"]
    if not modelVersions:
        util.printD("modelVersions is Empty")
        return

    version_strs = []
    for version in modelVersions:
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

    util.printD("Got following info for downloading:")
    util.printD(f"model_name: {model_name}")
    util.printD(f"model_type: {model_type}")
    util.printD(f"subfolders: {subfolders}")
    util.printD(f"version_strs: {version_strs}")

    return (model_info, model_name, model_type, subfolders, version_strs)

# get version info by version string
def get_ver_info_by_ver_str(version_str:str, model_info:dict) -> dict:
    if not version_str:
        util.printD("version_str is empty")
        return

    if not model_info:
        util.printD("model_info is None")
        return

    # get version list
    if "modelVersions" not in model_info.keys():
        util.printD("modelVersions is not in model_info")
        return

    modelVersions = model_info["modelVersions"]
    if not modelVersions:
        util.printD("modelVersions is Empty")
        return

    # find version by version_str
    version = None
    for ver in modelVersions:
        # version name can not be used as id
        # version id is not readable
        # so , we use name_id as version string
        ver_str = f'{ver["name"]}_{ver["id"]}'
        if ver_str == version_str:
            # find version
            version = ver

    if not version:
        util.printD(f"can not find version by version string: {version_str}")
        return

    # get version id
    if "id" not in version.keys():
        util.printD("this version has no id")
        return

    return version


# get download url from model info by version string
# return - (version_id, download_url)
def get_id_and_dl_url_by_version_str(version_str:str, model_info:dict) -> tuple:
    if not version_str:
        util.printD("version_str is empty")
        return

    if not model_info:
        util.printD("model_info is None")
        return

    # get version list
    if "modelVersions" not in model_info.keys():
        util.printD("modelVersions is not in model_info")
        return

    modelVersions = model_info["modelVersions"]
    if not modelVersions:
        util.printD("modelVersions is Empty")
        return

    # find version by version_str
    version = None
    for ver in modelVersions:
        # version name can not be used as id
        # version id is not readable
        # so , we use name_id as version string
        ver_str = f'{ver["name"]}_{ver["id"]}'
        if ver_str == version_str:
            # find version
            version = ver

    if not version:
        util.printD(f"Can not find version by version string: {version_str}")
        return

    # get version id
    if "id" not in version.keys():
        util.printD("This version has no id")
        return

    version_id = version["id"]
    if not version_id:
        util.printD("Version id is Empty")
        return

    # get download url
    if "downloadUrl" not in version.keys():
        util.printD("downloadUrl is not in this version")
        return

    downloadUrl = version["downloadUrl"]
    if not downloadUrl:
        util.printD("downloadUrl is Empty")
        return

    util.printD(f"Get Download Url: {downloadUrl}")

    return (version_id, downloadUrl)


def dl_model_by_input(model_info:dict, model_type:str, subfolder_str:str, version_str:str, dl_all_bool:bool, max_size_preview:bool, skip_nsfw_preview:bool, duplicate:str) -> str:
    """ download model from civitai by input
        output to markdown log
    """

    if not model_info:
        output = "model_info is None"
        util.printD(output)
        return output

    if not model_type:
        output = "model_type is None"
        util.printD(output)
        return output

    if not subfolder_str:
        output = "subfolder string is None"
        util.printD(output)
        return output

    if not version_str:
        output = "version_str is None"
        util.printD(output)
        return output

    # get model root folder
    if model_type not in model.folders.keys():
        output = f"Unknown model type: {model_type}"
        util.printD(output)
        return output

    model_root_folder = model.folders[model_type]


    # get subfolder
    subfolder = ""
    if subfolder_str == "/" or subfolder_str == "\\":
        subfolder = ""
    elif subfolder_str[:1] == "/" or subfolder_str[:1] == "\\":
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
        # get all download url from files info
        # some model versions have multiple files
        download_urls = []
        if "files" in ver_info.keys():
            for file_info in ver_info["files"]:
                if "downloadUrl" in file_info.keys():
                    download_urls.append(file_info["downloadUrl"])

        if not len(download_urls):
            if "downloadUrl" in ver_info.keys():
                download_urls.append(ver_info["downloadUrl"])


        # check if this model is already existed
        r = civitai.search_local_model_info_by_version_id(model_folder, version_id)
        if r:
            output = "This model version is already existed"
            util.printD(output)
            return output

        # download
        for url in download_urls:
            success, msg = downloader.dl(url, model_folder, None, None, duplicate)
            if not success:
                output = f"Downloading failed: {msg}"
                util.printD(output)
                return output

            if url == ver_info["downloadUrl"]:
                filepath = msg
    else:
        # only download one file
        # get download url
        url = ver_info["downloadUrl"]
        if not url:
            output = "Fail to get download url, check console log for detail"
            util.printD(output)
            return output

        # download
        success, msg = downloader.dl(url, model_folder, None, None, duplicate)
        if not success:
            output = f"Downloading failed: {msg}"
            util.printD(output)
            return output

        filepath = msg


    if not filepath:
        filepath = msg

    # get version info
    version_info = civitai.get_version_info_by_version_id(version_id)
    model.process_model_info(filepath, version_info, model_type)

    # then, get preview image
    civitai.get_preview_image_by_model_path(filepath, max_size_preview, skip_nsfw_preview)

    output = f"Done. Model downloaded to: {filepath}"
    util.printD(output)
    return output
