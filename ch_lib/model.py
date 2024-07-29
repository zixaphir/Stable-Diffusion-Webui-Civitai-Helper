""" -*- coding: UTF-8 -*-
Handle model operations
"""
import glob
import os
import json
import re
import urllib.parse
from PIL import Image
import piexif
import piexif.helper
from modules import shared
from modules import paths_internal
from . import civitai
from . import downloader
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

# Separate because the above is used for detecting supported models
# in other features
vae_folder = os.path.join(ROOT_PATH, "models", "VAE")


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


def local_image(model_info, img):
    """
    Check if a model_info already has a local download for the given image.
    return: The path to the local image, if it exists, otherwise None.
    """
    if "url" not in img:
        raise ValueError("No URL to fetch the image.")
    if "images" not in model_info:
        return None

    for eimg in model_info["images"]:
        if "url" not in eimg:
            continue
        if img["url"] == eimg["url"]:
            return eimg.get("local_file", None)

    return None


def next_example_image_path(model_path):
    """
    Find the next nonexistent path that can be used to store an example image.
    return: path:str
    """
    base_path, _ = os.path.splitext(model_path)
    i = 0
    while glob.glob(f"{base_path}.example.{i}.*"):
        i += 1
    return f"{base_path}.example.{i}"


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

    if shared.cmd_opts.vae_dir and os.path.isdir(shared.cmd_opts.vae_dir):
        vae_folder = shared.cmd_opts.vae_dir

    if util.get_opts("ch_dl_lyco_to_lora"):
        folders["lycoris"] = folders["lora"]

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


def locate_model_from_partial(root, model_name):
    """
        Tries to locate a model if the extension
        doesn't match the metadata
    """

    util.printD(model_name)

    for ext in EXTS:
        filename = os.path.join(root, f"{model_name}{ext}")
        if os.path.isfile(filename):
            return filename

    return None


def metadata_needed(info_file, sd15_file, refetch_old):
    """ return True if metadata is needed
    """

    need_civitai = metadata_needed_for_type(info_file, "civitai", refetch_old)
    need_sdwebui = metadata_needed_for_type(sd15_file, "sdwebui", refetch_old)

    return need_civitai or need_sdwebui


def metadata_needed_for_type(path, meta_type, refetch_old):
    """ return True if metadata is needed for path
    """

    if meta_type == "sdwebui" and not util.get_opts("ch_dl_webui_metadata"):
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
    existing_info = {}
    try:
        existing_info = load_model_info(info_file)
    except:
        util.printD("No existing model info.")

    clean_html = util.get_opts("ch_clean_html")

    parent = model_info["model"]

    description = parent.get("description", "")
    if description and clean_html:
        description = util.trim_html(description)
    parent["description"] = description

    version_description = model_info.get("description", "")
    if version_description and clean_html:
        version_description = util.trim_html(version_description)
    model_info["description"] = version_description

    # Create extension versioning information so that users
    # can replace stale info files without newer entries.
    model_info["extensions"] = util.create_extension_block(
        model_info.get("extensions", None),
        model_info.get("skeleton_file", False)
    )

    # Download preview images locally, for other extensions to display without
    # depending on civitai being up, or an internet connection at all.
    updated = False
    if util.get_opts("ch_download_examples"):
        images = model_info.get("images", [])

        for img in images:
            url = img.get("url", None)


            nsfw_preview_threshold = util.get_opts("ch_nsfw_threshold")
            rating = img.get("nsfwLevel", 32)
            if rating > 1:
                if civitai.NSFW_LEVELS[nsfw_preview_threshold] < rating:
                    continue

            if url:
                existing_dl = local_image(existing_info, img)
                if existing_dl:
                    # Ensure it's set in the new model info.
                    img["local_file"] = existing_dl

                else:
                    # Fetch it, save it, set it in the model info.
                    path = urllib.parse.urlparse(url).path
                    _, ext = os.path.splitext(path)
                    outpath = next_example_image_path(model_path) + ext

                    for result in downloader.dl_file(
                            url,
                            folder=os.path.dirname(outpath),
                            filename=os.path.basename(outpath)):
                        if not isinstance(result, str):
                            success, output = result
                            break

                    if not success:
                        downloader.error(url, "Failed to download model image.")
                        continue

                    img["local_file"] = outpath
                    updated = True

    # civitai model info file
    if metadata_needed_for_type(info_file, "civitai", refetch_old) or updated:
        if refetch_old:
            try:
                if verify_overwrite_eligibility(info_file, model_info):
                    write_info(model_info, info_file, "civitai")

            except VersionMismatchException as e:
                util.printD(f"{e}, aborting")
                return

        else:
            write_info(model_info, info_file, "civitai")

    if not util.get_opts("ch_dl_webui_metadata"):
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
    #
    # I'm populating the field anyways in hopes it eventually gets
    # added.
    base_model = model_info.get("baseModel", None)
    sd_version = 'Unknown'
    if base_model:
        version = None
        try:
            version = base_model[3]
        except IndexError:
            version = 0

        sd_version = {
            "1": 'SD1',
            "2": 'SD2',
            "L": 'SDXL',
        }.get(version, 'Unknown')

    sd_data["sd version"] = sd_version

    for filedata in model_info["files"]:
        if filedata["type"] == "VAE":
            sd_data["vae"] = filedata["name"]

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

    sd_data["extensions"] = util.create_extension_block(
        model_info.get("extensions", None),
        model_info.get("skeleton_file", False)
    )

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
        except ValueError:
            util.printD(f"Selected file is not json: {path}")
            return None

    return model_info


def get_potential_model_preview_files(model_path, all_prevs=False):
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
        if all_prevs:
            preview_files.append(f"{base}.{ext}")
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
    if not model_name:
        util.printD("model name can not be empty")
        return None

    model_folders = [folders.get(model_type, None)]

    if model_folders[0] is None:
        util.printD(f"unknown model_type: {model_type}")
        return None

    if model_type == "lora" and folders['lycoris']:
        model_folders.append(folders['lycoris'])

    # model could be in subfolder, need to walk.
    model_path = util.find_file_in_folders(model_folders, model_name)

    msg = util.indented_msg(f"""
        Got following info:
        {model_path=}
    """)
    util.printD(msg)

    # May return `None`
    return model_path


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
        util.printD("Unknown model type: " + model_type)
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

    msg = util.indented_msg(f"""
        Got following info:
        {model_folder=}
        {model_sub_path=}
        {model_path=}
    """)
    util.printD(msg)

    if not os.path.isfile(model_path):
        util.printD(f"Can not find model file: {model_path}")
        return None

    return model_path


# pattern = re.compile(r"\s*([^:,]+):\s*([^,]+)")

# def sd_format(data):
#     """
#     Parse image exif data for image creation parameters.
#
#     return parameters:dict or None
#     """
#
#     if not data:
#         return None
#
#     prompt = ""
#     negative = ""
#     setting = ""
#
#     steps_index = data.find("\nSteps:")
#
#     if steps_index != -1:
#         prompt = data[:steps_index].strip()
#         setting = data[steps_index:].strip()
#
#     if "Negative prompt:" in data:
#         prompt_index = data.find("\nNegative prompt:")
#
#         if steps_index != -1:
#             negative = data[
#                 prompt_index + len("Negative prompt:") + 1 : steps_index
#             ].strip()
#
#         else:
#             negative = data[
#                 prompt_index + len("Negative prompt:") + 1 :
#             ].strip()
#
#         prompt = data[:prompt_index].strip()
#
#     elif steps_index == -1:
#         prompt = data
#
#     setting_dict = dict(re.findall(pattern, setting))
#
#     data = {
#          "prompt": prompt,
#          "negative": negative,
#          "Steps": setting_dict.get("Steps", ""),
#          "Sampler": setting_dict.get("Sampler", ""),
#          "CFG_scale": setting_dict.get("CFG scale", ""),
#          "Seed": setting_dict.get("Seed", ""),
#          "Size": setting_dict.get("Size", ""),
#     }
#
#     return data


# def parse_image(image_file):
#     """
#     Read image exif for userComment entry.
#     return: userComment:str
#     """
#     data = None
#     with Image.open(image_file) as image:
#         if image.format == "PNG":
#             # However, unlike other image formats, EXIF data is not
#             # guaranteed to be present in info until load() has been called.
#             # https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#png
#             image.load()
#             data = image.info.get("parameters")
#
#         elif image.format in ["JPEG", "WEBP"]:
#             try:
#                 usercomment = piexif.ExifIFD.UserComment
#                 exif = image.info.get("exif")
#                 if not exif:
#                     return None
#                 jpegexif = piexif.load(exif) or {}
#                 data = piexif.helper.UserComment.load(
#                     jpegexif.get("Exif", {}).get(usercomment, None)
#                 )
#
#             except (ValueError, TypeError):
#                 util.printD("Failed to parse image exif.")
#                 return None
#
#     return data


# def get_remote_image_info(img_src):
#     """
#     Download a remote image and parse out its creation parameters
#
#     return parameters:dict or None
#     """
#     # anti-DDOS protection
#     util.delay(0.2)
#
#     success, response = downloader.request_get(img_src)
#
#     if not success:
#         return None
#
#     image_file = response.raw
#     try:
#         data = parse_image(image_file)
#
#     except OSError: #, UnidentifiedImageError
#         util.printD("Failed to open image.")
#         return None
#
#     if not data:
#         return None
#
#     sd_data = sd_format(data)
#     return sd_data


# def update_civitai_info_image_meta(filename):
#     """
#     Read model metadata and update missing image creation parameters,
#     if available.
#     """
#     need_update = False
#     data = {}
#
#     if not os.path.isfile(filename):
#         return
#
#     with open(filename, 'r') as model_json:
#         data = json.load(model_json)
#
#     for img in data.get('images', []):
#
#         nsfw_preview_threshold = util.get_opts("ch_nsfw_threshold")
#         rating = img.get("nsfwLevel", 32)
#         if rating > 1:
#             if civitai.NSFW_LEVELS[nsfw_preview_threshold] < rating:
#                 continue
#
#         metadata = img.get('meta', None)
#         if not metadata and metadata != {}:
#             url = img.get("url", "")
#             if not url:
#                 continue
#
#             util.printD(f"{filename} missing generation info for {url}. Processing {url}.")
#
#             img_data = get_remote_image_info(url)
#             if not img_data:
#                 util.printD(f"Failed to find generation info on remote image at {url}.")
#
#                 # "mark" image so additional runs will skip it.
#                 img["meta"] = {}
#                 need_update = True
#                 continue
#
#             util.printD(
#                 "The following information will be added to "
#                 f"{filename} for {url}:\n{img_data}"
#             )
#             metadata = img_data
#             img["meta"] = metadata
#
#             need_update = True
#
#     if need_update:
#         with open(filename, 'w') as info_file:
#             json.dump(data, info_file, indent=4)


def scan_civitai_info_image_meta():
    """ Search for *.civitai.info files """
    util.printD("Start Scan_civitai_info_image_meta")
    output = ""
    count = 0

    directories = [y for x, y in folders.items() if os.path.isdir(y)]
    util.printD(f"{directories=}")
    for directory in directories:
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename.endswith('.civitai.info'):
                    update_civitai_info_image_meta(os.path.join(root, filename))
                    count = count + 1

    output = f"Done. Scanned {count} files."
    util.printD(output)
    return output
