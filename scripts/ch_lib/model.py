# -*- coding: UTF-8 -*-
# handle msg between js and python side
import os
import json
from . import civitai
from . import util
from modules import shared, paths_internal


# this is the default root path
ROOT_PATH = paths_internal.data_path

EXTS = (".bin", ".pt", ".safetensors", ".ckpt")
CIVITAI_EXT = ".info"
SDWEBUI_EXT = ".json"

"""
If command line arguement is used to change model folder,
then model folder is in absolute path, not based on this root path anymore.
so to make extension work with those absolute model folder paths, model folder also need to be in absolute path
"""
folders = {
    "ti": os.path.join(ROOT_PATH, "embeddings"),
    "hyper": os.path.join(ROOT_PATH, "models", "hypernetworks"),
    "ckp": os.path.join(ROOT_PATH, "models", "Stable-diffusion"),
    "lora": os.path.join(ROOT_PATH, "models", "Lora"),
    "lycoris": os.path.join(ROOT_PATH, "models", "LyCORIS"),
}


class VersionMismatchException(Exception):
    # Constructor or Initializer
    def __init__(self, value):
        self.value = value

    # __str__ is to print() the value
    def __str__(self):
        return(repr(self.value))


def get_model_info_paths(model_path):
    base, ext = os.path.splitext(model_path)
    info_file = f"{base}{civitai.SUFFIX}{CIVITAI_EXT}"
    sd15_file = f"{base}{SDWEBUI_EXT}"
    return (info_file, sd15_file)


# get custom model path
def get_custom_model_folder():
    util.printD("Get Custom Model Folder")

    global folders

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
        if shared.cmd_opts.lyco_dir and os.path.isdir(shared.cmd_opts.lyco_dir):
            folders["lycoris"] = shared.cmd_opts.lyco_dir

    except:
        try:
            # sd-webui v1.5.1 added a backcompat option for lyco.
            if shared.cmd_opts.lyco_dir_backcompat and os.path.isdir(shared.cmd_opts.lyco_dir_backcompat):
                folders["lycoris"] = shared.cmd_opts.lyco_dir_backcompat
        except:
            # XXX v1.5.0 has no options for the Lyco dir: it is hardcoded as 'os.path.join(paths.models_path, "LyCORIS")'
            pass


def process_key_error(note):
    util.printD(f"Failed to process {note}. Continuing.")


def metadata_needed(info_file, sd15_file, refetch_old):
    """ return True if metadata is needed
    """

    need_civitai = metadata_needed_for_type(info_file, "civitai", refetch_old)
    need_sdwebui = metadata_needed_for_type(sd15_file, "sdwebui", refetch_old)

    return need_civitai or need_sdwebui


def metadata_needed_for_type(path, meta_type, refetch_old):
    """ return True if metadata is needed for path
    """
    if not os.path.isfile(path):
        return True

    if refetch_old:
        metadata = None
        with open(path) as file:
            metadata = json.load(file)

        metadata_version = util.metadata_version(metadata)

        if not metadata_version:
            return True

        compat_version = util.COMPAT_VERSION_CIVITAI if meta_type == "civitai" else util.COMPAT_VERSION_SDWEBUI

        util.printD(f"{path}: {metadata_version}, {compat_version}")

        return util.newer_versions(compat_version, metadata_version)

    return False


def verify_overwrite_eligibility(path, new_data):
    if not os.path.isfile(path):
        return True

    with open(path, "r") as file:
        old_data = json.load(file)

    if "civitai" in path:
        new_id = new_data.get("id", "")
        old_id = old_data.get("id", "")
        if new_id != old_id:
            if old_id != "":
                raise VersionMismatchException(f"New metadata id ({new_id}) does not match old metadata id ({old_id})")

    if new_data.get("description", "") == "" and old_data.get("description", "") != "":
        util.printD(f"New description is blank while old description contains data. Skipping {path}")
        return False

    return True


def process_model_info(model_path, model_info, model_type="ckp", refetch_old=False):
    """ Write model info to file

        SD1.5 Webui added saving model information to JSON files.
        Much of this extension's metadata management is replicated
        by this new functionality, including automatically adding
        activator keywords to the prompt. It also provides a much
        cleaner UI than civitai (not a high bar to clear) to
        simply read a model's description.

        So why not populate it with useful information?

        Returns True if successful, otherwise an error message.
    """

    def write_info(data, path, info_type):
        util.printD(f"Write model {info_type} info to file: {path}")
        with open(os.path.realpath(path), 'w') as f:
            f.write(json.dumps(data, indent=4))

    if model_info is None:
        util.printD(f"Failed to get model info.")
        return

    info_file, sd15_file = get_model_info_paths(model_path)

    parent = model_info["model"]

    try:
        parent["description"] = util.trim_html(parent["description"])

    except Exception:
        parent["description"] = ""
        process_key_error("model description")

    try:
        model_info["description"] = util.trim_html(model_info["description"])

    except Exception:
        model_info["description"] = ""
        process_key_error("version description")

    try:
        tags = parent["tags"]
        data = []
        for tag in tags:
            data.append(tag)

        parent["tags"] = data

    except Exception as e:
        parent["tags"] = []
        process_key_error("tags")

    """
    I'm already running into issues with people asking for breaking
    changes, so I just want to have this for reference later down
    the line
    """
    model_info["extensions"] = util.create_extension_block(model_info.get("extensions", {}))

    ### civitai model info file
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

    ### sd v1.5 model info file
    sd_data = {}

    # Do not overwrite user-created files!
    # TODO: maybe populate empty fields in existing files?
    if not metadata_needed_for_type(sd15_file, "sdwebui", refetch_old):
        util.printD(f"Metadata not needed for: {sd15_file}.")
        return

    util.printD(f"Write model SD webui info to file: {sd15_file}")

    sd_data["description"] = parent.get("description", "")

    """
    I suppose notes are more for user notes, but populating it
    with potentially useful information about this particular
    version of the model is fine too, right? The user can
    always replace these if they're unneeded or add to them
    """
    version_info = model_info.get("description", None)
    if version_info is not None:
        sd_data["notes"] = version_info

    """
    AFAIK civitai model versions are currently:
    SD 1.4, SD 1.5, SD 2.0, SD 2.0 786, SD 2.1, SD 2.1 786
    SD 2.1 Unclip, SDXL 0.9, SDXL 1.0, and Other.
    Conveniently, the 4th character is all we need for webui.

    INFO: On Civitai, all models list base model/"sd version".
    The SD WebUI interface only displays them for Lora/Lycoris.
    I'm populating the field anyways in hopes it eventually gets
    added.
    """
    base_model = model_info.get("baseModel", None)
    if base_model:
        sd_version = base_model[3]

        if sd_version == '1':
            sd_version = 'SD1'
        elif sd_version ==  '2':
            sd_version = 'SD2'
        elif sd_version == 'L':
            sd_version = 'SDXL'
        else:
            sd_version = 'Unknown'
    else:
        sd_version = 'Unknown'

    sd_data["sd version"] = sd_version

    """
    INFO: On Civitai, all non-checkpoint models can have trained words.
    The SD WebUI interface only displays them for Lora/Lycoris.
    I'm populating the field anyways in hopes it eventually gets
    added.

    "trained words" usage is inconsistent among model authors.
    Some use each entry as an individual activator, while others
    use them as entire prompts
    """
    activator = model_info.get("trainedWords", [])
    if (activator and activator[0]):
        if "," in activator[0]:
            # assume trainedWords is a prompt list

            """
            XXX webui does not support newlines in activator text
            so this is the best hinting I can give the user at the
            moment that these are mutually-exclusive prompts.
            """
            sd_data["activation text"] = " || ".join(activator)
        else:
            # assume trainedWords are single keywords
            sd_data["activation text"] = ", ".join(activator)

    """
    Sadly, Civitai does not provide default weight information,
    So 0 disables this functionality on webui's end
    (Tho 1 would also work?)
    """

    if model_type in ["lora", "lycoris"]:
        sd_data["preferred weight"] = 0

    sd_data["extensions"] = util.create_extension_block(sd_data.get("extensions", None))

    if refetch_old:
        if verify_overwrite_eligibility(sd15_file, sd_data):
            write_info(sd_data, sd15_file, "webui")
    else:
        write_info(sd_data, sd15_file, "webui")


def load_model_info(path):
    # util.printD(f"Load model info from file: {path}")
    model_info = None
    with open(os.path.realpath(path), 'r') as f:
        try:
            model_info = json.load(f)
        except Exception as e:
            util.printD(f"Selected file is not json: {path}")
            util.printD(e)
            return

    return model_info


# get model file names by model type
# parameter: model_type - string
# return: model name list
def get_model_names_by_type(model_type:str) -> list:

    if model_type == "lora" and folders['lycoris']:
        model_folders = [folders[model_type], folders['lycoris']]
    else:
        model_folders = [folders[model_type]]

    # get information from filter
    # only get those model names don't have a civitai model info file
    model_names = []
    for model_folder in model_folders:
        for root, dirs, files in os.walk(model_folder, followlinks=True):
            for filename in files:
                item = os.path.join(root, filename)
                # check extension
                base, ext = os.path.splitext(item)
                if ext in EXTS:
                    # find a model
                    model_names.append(filename)


    return model_names


# return 2 values: (model_root, model_path)
def get_model_path_by_type_and_name(model_type:str, model_name:str) -> str:
    util.printD("Run get_model_path_by_type_and_name")
    if model_type not in folders.keys():
        util.printD(f"unknown model_type: {model_type}")
        return

    if not model_name:
        util.printD("model name can not be empty")
        return

    if model_type == "lora" and folders['lycoris']:
        model_folders = [folders[model_type], folders['lycoris']]
    else:
        model_folders = [folders[model_type]]


    # model could be in subfolder, need to walk.
    model_root = ""
    model_path = ""
    for folder in model_folders:
        for root, dirs, files in os.walk(folder, followlinks=True):
            for filename in files:
                if filename == model_name:
                    # find model
                    model_root = root
                    model_path = os.path.join(root, filename)
                    return (model_root, model_path)

    return



