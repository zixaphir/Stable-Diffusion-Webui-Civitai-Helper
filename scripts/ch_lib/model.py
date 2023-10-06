""" -*- coding: UTF-8 -*-
Handle model operations
"""
import os
import json
from modules import shared
from modules import paths_internal
from modules.shared import opts
from . import civitai
from . import util


# this is the default root path
ROOT_PATH = paths_internal.data_path

EXTS = (".bin", ".pt", ".safetensors", ".ckpt")
CIVITAI_EXT = ".info"
SDWEBUI_EXT = ".json"

"""
If command line arguement is used to change model folder,
then model folder is in absolute path, not based on this root path anymore.
so to make extension work with those absolute model folder paths, model
folder also need to be in absolute path
"""
folders = {
    "ti": os.path.join(ROOT_PATH, "embeddings"),
    "hyper": os.path.join(ROOT_PATH, "models", "hypernetworks"),
    "ckp": os.path.join(ROOT_PATH, "models", "Stable-diffusion"),
    "lora": os.path.join(ROOT_PATH, "models", "Lora"),
    "lycoris": os.path.join(ROOT_PATH, "models", "LyCORIS"),
}


class VersionMismatchException(Exception):
    """ Used for version comarison failures """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def get_model_info_paths(model_path):
    """
    Retrieve model info paths
    return: (info_file:str, sd15_file:str)
    """
    base, _ = os.path.splitext(model_path)
    info_file = f"{base}{civitai.SUFFIX}{CIVITAI_EXT}"
    sd15_file = f"{base}{SDWEBUI_EXT}"
    return (info_file, sd15_file)


# get custom model path
def get_custom_model_folder():
    """
    Update extra network directories with user-specified values.
    """
    util.printD("Get Custom Model Folder")

    if shared.cmd_opts.embeddings_dir and os.path.isdir(shared.cmd_opts.embeddings_dir):
        folders["ti"] = shared.cmd_opts.embeddings_dir

    if shared.cmd_opts.hypernetwork_dir and os.path.isdir(shared.cmd_opts.hypernetwork_dir):
        folders["hyper"] = shared.cmd_opts.hypernetwork_dir

    if shared.cmd_opts.ckpt_dir and os.path.isdir(shared.cmd_opts.ckpt_dir):
        folders["ckp"] = shared.cmd_opts.ckpt_dir

    if shared.cmd_opts.lora_dir and os.path.isdir(shared.cmd_opts.lora_dir):
        folders["lora"] = shared.cmd_opts.lora_dir

    try:
        # pre-1.5.0
        if os.path.isdir(shared.cmd_opts.lyco_dir):
            folders["lycoris"] = shared.cmd_opts.lyco_dir

    except AttributeError:
        try:
            # sd-webui v1.5.1 added a backcompat option for lyco.
            if os.path.isdir(shared.cmd_opts.lyco_dir_backcompat):
                folders["lycoris"] = shared.cmd_opts.lyco_dir_backcompat
        except AttributeError:
            # v1.5.0 has no options for the Lyco dir:
            # it is hardcoded as 'os.path.join(paths.models_path, "LyCORIS")'
            return


def metadata_needed(info_file, sd15_file, refetch_old):
    """ return True if metadata is needed
    """

    need_civitai = metadata_needed_for_type(info_file, "civitai", refetch_old)
    need_sdwebui = metadata_needed_for_type(sd15_file, "sdwebui", refetch_old)

    return need_civitai or need_sdwebui


def metadata_needed_for_type(path, meta_type, refetch_old):
    """ return True if metadata is needed for path
    """

    if meta_type == "sdwebui" and not opts.ch_dl_webui_metadata:
        return False

    if not os.path.isfile(path):
        return True

    if refetch_old:
        metadata = None
        with open(path) as file:
            metadata = json.load(file)

        metadata_version = util.metadata_version(metadata)

        if not metadata_version:
            return True

        if meta_type == "civitai":
            compat_version = util.COMPAT_VERSION_CIVITAI
        else:
            compat_version = util.COMPAT_VERSION_SDWEBUI

        util.printD(f"{path}: {metadata_version}, {compat_version}")

        return util.newer_version(compat_version, metadata_version)

    return False


def verify_overwrite_eligibility(path, new_data):
    """
    Verifies a file is valid to be overwritten
    Throws an error if the model ID does not match the new version's model ID
    return: True if valid, False if not.
    """
    if not os.path.isfile(path):
        return True

    with open(path, "r") as file:
        old_data = json.load(file)

    if "civitai" in path:
        new_id = new_data.get("id", "")
        old_id = old_data.get("id", "")
        if new_id != old_id:
            if old_id != "":
                raise VersionMismatchException(
                    f"New metadata id ({new_id}) does not match old metadata id ({old_id})"
                )

    new_description = new_data.get("description", "")
    old_description = old_data.get("description", "")
    if new_description == "" and old_description != "":
        util.printD(
            f"New description is blank while old description contains data. Skipping {path}"
        )
        return False

    return True


def write_info(data, path, info_type):
    """ Writes model info to a file """
    util.printD(f"Write model {info_type} info to file: {path}")
    with open(os.path.realpath(path), 'w') as info_file:
        info_file.write(json.dumps(data, indent=4))


def process_model_info(model_path, model_info, model_type="ckp", refetch_old=False):
    """
    Write model info to file

    SD1.5 Webui added saving model information to JSON files.
    Much of this extension's metadata management is replicated
    by this new functionality, including automatically adding
    activator keywords to the prompt. It also provides a much
    cleaner UI than civitai (not a high bar to clear) to
    simply read a model's description.

    So why not populate it with useful information?

    Returns True if successful, otherwise an error message.
    """

    if model_info is None:
        util.printD("Failed to get model info.")
        return

    info_file, sd15_file = get_model_info_paths(model_path)

    parent = model_info["model"]

    description = parent.get("description", "")
    if description:
        description = util.trim_html(description)
    parent["description"] = description

    version_description = model_info.get("description", "")
    if version_description:
        version_description = util.trim_html(version_description)
    model_info["description"] = version_description

    tags = parent.get("tags", [])
    parent["tags"] = tags

    # Create extension versioning information so that users
    # can replace stale info files without newer entries.
    model_info["extensions"] = util.create_extension_block(model_info.get("extensions", {}))

    # civitai model info file
    if metadata_needed_for_type(info_file, "civitai", refetch_old):
        if refetch_old:
            try:
                if verify_overwrite_eligibility(info_file, model_info):
                    write_info(model_info, info_file, "civitai")
            except VersionMismatchException as e:
                util.printD(f"{e}, aborting")
                return
        else:
            write_info(model_info, info_file, "civitai")

    if not opts.ch_dl_webui_metadata:
        return

    # Do not overwrite user-created files!
    # TODO: maybe populate empty fields in existing files?
    if not metadata_needed_for_type(sd15_file, "sdwebui", refetch_old):
        util.printD(f"Metadata not needed for: {sd15_file}.")
        return

    process_sd15_info(sd15_file, model_info, parent, model_type, refetch_old)


def process_sd15_info(sd15_file, model_info, parent, model_type, refetch_old):
    """ Creates/Processes [model_name].json """

    # sd v1.5 model info file
    sd_data = {}

    util.printD(f"Write model SD webui info to file: {sd15_file}")

    sd_data["description"] = parent.get("description", "")

    # I suppose notes are more for user notes, but populating it
    # with potentially useful information about this particular
    # version of the model is fine too, right? The user can
    # always replace these if they're unneeded or add to them
    version_info = model_info.get("description", None)
    if version_info is not None:
        sd_data["notes"] = version_info

    # AFAIK civitai model versions are currently:
    # SD 1.4, SD 1.5, SD 2.0, SD 2.0 786, SD 2.1, SD 2.1 786
    # SD 2.1 Unclip, SDXL 0.9, SDXL 1.0, and Other.
    # Conveniently, the 4th character is all we need for webui.
    #
    # INFO: On Civitai, all models list base model/"sd version".
    # The SD WebUI interface only displays them for Lora/Lycoris.
    # I'm populating the field anyways in hopes it eventually gets
    # added.
    base_model = model_info.get("baseModel", None)
    sd_version = 'Unknown'
    if base_model:
        version = base_model[3]

        sd_version = {
            "1": 'SD1',
            "2": 'SD2',
            "L": 'SDXL',
        }.get(version, 'Unknown')

    sd_data["sd version"] = sd_version

    # INFO: On Civitai, all non-checkpoint models can have trained words.
    # The SD WebUI interface only displays them for Lora/Lycoris.
    # I'm populating the field anyways in hopes it eventually gets
    # added.
    #
    # "trained words" usage is inconsistent among model authors.
    # Some use each entry as an individual activator, while others
    # use them as entire prompts
    activator = model_info.get("trainedWords", [])
    if (activator and activator[0]):
        if "," in activator[0]:
            # assume trainedWords is a prompt list

            # webui does not support newlines in activator text
            # so this is the best hinting I can give the user at the
            # moment that these are mutually-exclusive prompts.
            sd_data["activation text"] = " || ".join(activator)
        else:
            # assume trainedWords are single keywords
            sd_data["activation text"] = ", ".join(activator)

    # Sadly, Civitai does not provide default weight information,
    # So 0 disables this functionality on webui's end and uses
    # the user's global setting
    if model_type in ["lora", "lycoris"]:
        sd_data["preferred weight"] = 0

    sd_data["extensions"] = util.create_extension_block(sd_data.get("extensions", None))

    if refetch_old:
        if verify_overwrite_eligibility(sd15_file, sd_data):
            write_info(sd_data, sd15_file, "webui")
    else:
        write_info(sd_data, sd15_file, "webui")


def load_model_info(path):
    """ Opens a JSON file and loads its JSON """
    model_info = None
    with open(os.path.realpath(path), 'r') as json_file:
        try:
            model_info = json.load(json_file)
        except ValueError as e:
            util.printD(f"Selected file is not json: {path}")
            util.printD(e)
            return None

    return model_info


def get_potential_model_preview_files(model_path):
    """
    Find existing preview images, if any.

    Extensions from `find_preview` method in webui `modules/ui_extra_networks.py`
    gif added in webui commit c602471b85d270e8c36707817d9bad92b0ff991e

    return: preview_files
    """
    preview_exts = ["png", "jpg", "jpeg", "webp", "gif"]
    preview_files = []

    base, _ = os.path.splitext(model_path)

    for ext in preview_exts:
        preview_files.append(f"{base}.preview.{ext}")

    return preview_files


def get_model_files_from_model_path(model_path):
    """ return: list of paths """

    base, _ = os.path.splitext(model_path)

    info_file, sd15_file = get_model_info_paths(model_path)
    user_preview_path = f"{base}.png"

    paths = [model_path, info_file, sd15_file, user_preview_path]
    preview_paths = get_potential_model_preview_files(model_path)

    paths = paths + preview_paths

    return [path for path in paths if os.path.isfile(path)]


def get_model_names_by_type(model_type:str) -> list:
    """
    get model file names by model type
    parameter: model_type - string
    return: model name list
    """

    if model_type == "lora" and folders['lycoris']:
        model_folders = [folders[model_type], folders['lycoris']]
    else:
        model_folders = [folders[model_type]]

    # get information from filter
    # only get those model names don't have a civitai model info file
    model_names = []
    for model_folder in model_folders:
        for root, _, files in os.walk(model_folder, followlinks=True):
            for filename in files:
                item = os.path.join(root, filename)
                # check extension
                _, ext = os.path.splitext(item)
                if ext in EXTS:
                    # find a model
                    model_names.append(filename)

    return model_names


# return 2 values: (model_root, model_path)
def get_model_path_by_type_and_name(model_type:str, model_name:str) -> str:
    """ return: model_path:str matching model_name and model_type """
    util.printD("Run get_model_path_by_type_and_name")
    if folders.get(model_type, None) is None:
        util.printD(f"unknown model_type: {model_type}")
        return None

    if not model_name:
        util.printD("model name can not be empty")
        return None

    if model_type == "lora" and folders['lycoris']:
        model_folders = [folders[model_type], folders['lycoris']]
    else:
        model_folders = [folders[model_type]]


    # model could be in subfolder, need to walk.
    model_root = ""
    model_path = ""
    for folder in model_folders:
        for root, _, files in os.walk(folder, followlinks=True):
            for filename in files:
                if filename == model_name:
                    # find model
                    model_root = root
                    model_path = os.path.join(root, filename)
                    return (model_root, model_path)

    return None


# get model path by model type and search_term
# parameter: model_type, search_term
# return: model_path
def get_model_path_by_search_term(model_type, search_term):
    """
    Gets a model path based on the webui search term.

    return: model_path
    """
    util.printD(f"Search model of {search_term} in {model_type}")
    if folders.get(model_type, None) is None:
        util.printD("unknow model type: " + model_type)
        return None

    # for lora: search_term = subfolderpath + model name + ext + " " + hash.
    #   And it always start with a / even there is no sub folder
    # for ckp: search_term = subfolderpath + model name + ext + " " + hash
    # for ti: search_term = subfolderpath + model name + ext + " " + hash
    # for hyper: search_term = subfolderpath + model name

    # this used to be
    # `model_sub_path = search_term.split()[0]`
    # but it was failing on models containing spaces.
    model_hash = search_term.split()[-1]
    model_sub_path = search_term.replace(f" {model_hash}", "")

    if model_type == "hyper":
        model_sub_path = f"{search_term}.pt"

    if model_sub_path[:1] == "/":
        model_sub_path = model_sub_path[1:]

    if model_type == "lora" and folders['lycoris']:
        model_folders = [folders[model_type], folders['lycoris']]
    else:
        model_folders = [folders[model_type]]

    for folder in model_folders:
        model_folder = folder
        model_path = os.path.join(model_folder, model_sub_path)

        if os.path.isfile(model_path):
            break

    util.printD(util.dedent(f"""
        Got following info:")
        * model_folder: {model_folder}
        * model_sub_path: {model_sub_path}
        * model_path: {model_path}
    """))

    if not os.path.isfile(model_path):
        util.printD(f"Can not find model file: {model_path}")
        return None

    return model_path
