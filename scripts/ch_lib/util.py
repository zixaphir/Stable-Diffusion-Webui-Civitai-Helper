""" -*- coding: UTF-8 -*-
Utility functions for Stable Diffusion Civitai Helper
"""
from __future__ import annotations
import os
import io
import re
import hashlib
import textwrap
import time
import subprocess
import gradio as gr
from modules import shared
from modules.shared import opts
from modules import hashes
import launch
from packaging.version import parse as parse_version

try:
    # Automatic1111 SD WebUI
    import modules.cache as sha256_cache
except ModuleNotFoundError:
    # Vladmandic "SD.Next"
    import modules.hashes as sha256_cache

# used to append extension information to JSON/INFO files
SHORT_NAME = "sd_civitai_helper"

# current version of the exension
VERSION = "1.8.3"

# Civitai INFO files below this version will regenerated
COMPAT_VERSION_CIVITAI = "1.7.2"

# SD webui model info JSON below this version will be regenerated
COMPAT_VERSION_SDWEBUI = "1.8.0"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    )
}

PROXIES = {
    "http": None,
    "https": None,
}

REQUEST_TIMEOUT = 300  # 5 minutes
REQUEST_RETRIES = 5

_MINUTE = 60
_HOUR = _MINUTE * 60
_DAY = _HOUR * 24


# print for debugging
def printD(msg:any) -> str:
    """ Print a message to stderr """
    print(f"CHv{VERSION}: {msg}")


def append_default_headers(headers:dict) -> dict:
    """ Append extension default values to customized headers where missing """

    for key, val in DEFAULT_HEADERS.items():
        if key not in headers:
            headers[key] = val
    return headers


def indented_msg(msg:str) -> str:
    """
    Clean up an indented message in the format of
    [header]
    var1=var1
    var2=var2
    var3=var3

    and print the results in the format of:

    Civitai Helper: [header]
        var1: var1
        var2: var2
        var3: var3

    return: msg:str
    """

    msg_parts = textwrap.dedent(
        msg
    ).strip().split('\n')
    msg = [msg_parts.pop(0)]
    for part in msg_parts:
        part = ": ".join(part.split("="))
        msg.append(f"   {part}")
    msg = "\n".join(msg)

    return msg


def delay(seconds:float) -> None:
    """ delay before next request, mostly to prevent being treated as a DDoS """
    time.sleep(seconds)


def is_stale(timestamp:float) -> bool:
    """ Returns if a timestamp was more than a day ago. """
    cur_time = ch_time()
    elapsed = cur_time - timestamp

    if elapsed > _DAY:
        return True

    return False


def info(msg:str) -> None:
    """ Display an info smessage on the client DOM """
    gr.Info(msg)


def warning(msg:str) -> None:
    """ Display a warning message on the client DOM """
    gr.Warning(msg)


def error(msg:str) -> None:
    """ Display an error message on the client DOM """
    gr.Error(msg)


def ch_time() -> int:
    """ Unix timestamp """
    return int(time.time())


def dedent(text:str) -> str:
    """ alias for textwrap.dedent """
    return textwrap.dedent(text)


def get_name(model_path:str, model_type:str) -> str:
    """ return: {model_type}/{model_name} """

    model_name = os.path.splitext(os.path.basename(model_path))[0]
    return f"{model_type}/{model_name}"


def get_opts(key):
    """ return: option value """
    return opts.data.get(key, None)


def gen_file_sha256(filename:str, model_type="lora", use_addnet_hash=False) -> str:
    """ return a sha256 hash for a file """

    cache = sha256_cache.cache
    dump_cache = sha256_cache.dump_cache
    model_name = get_name(filename, model_type)

    sha256_hashes = None
    if use_addnet_hash:
        sha256_hashes = cache("hashes-addnet")
    else:
        sha256_hashes = cache("hashes")

    sha256_value = hashes.sha256_from_cache(filename, model_name, use_addnet_hash)
    if sha256_value is not None:
        yield sha256_value
        return

    if shared.cmd_opts.no_hashing:
        printD("SD WebUI Civitai Helper requires hashing functions for this feature. \
            Please remove the commandline argument `--no-hashing` for this functionality.")
        yield None
        return

    with open(filename, "rb") as model_file:
        result = None
        for result in calculate_sha256(model_file, use_addnet_hash):
            yield result
        sha256_value = result

    printD(f"sha256: {sha256_value}")

    sha256_hashes[model_name] = {
        "mtime": os.path.getmtime(filename),
        "sha256": sha256_value,
    }

    dump_cache()

    yield sha256_value

def calculate_sha256(model_file, use_addnet_hash=False):
    """ calculate the sha256 hash for a model file """

    blocksize= 1 << 20
    sha256_hash = hashlib.sha256()

    size = os.fstat(model_file.fileno()).st_size

    offset = 0
    if use_addnet_hash:
        model_file.seek(0)
        header= model_file.read(8)
        offset = int.from_bytes(header, "little") + 8
        model_file.seek(offset)

    pos = 0
    for block in read_chunks(model_file, size=blocksize):
        pos += len(block)

        percent = (pos - offset) / (size - offset)

        yield (percent, f"hashing model {model_file.name}")

        sha256_hash.update(block)

    hash_value =  sha256_hash.hexdigest()
    yield hash_value


def read_chunks(file, size=io.DEFAULT_BUFFER_SIZE) -> bytes:
    """ Yield pieces of data from a file-like object until EOF. """
    while True:
        chunk = file.read(size)
        if not chunk:
            break
        yield chunk


def get_subfolders(folder:str) -> list[str]:
    """ return: list of subfolders """
    printD(f"Get subfolder for: {folder}")
    if not folder:
        printD("folder can not be None")
        return []

    if not os.path.isdir(folder):
        printD("path is not a folder")
        return []

    prefix_len = len(folder)
    full_dirs_searched = []
    subfolders = []
    for root, dirs, _ in os.walk(folder, followlinks=True):
        if root == folder:
            continue

        # Prevent following recursive symlinks
        follow = []
        for directory in dirs:
            full_dir_path = os.path.join(root, directory)
            try:
                canonical_dir = os.path.realpath(full_dir_path, strict=True)
                if canonical_dir not in full_dirs_searched:
                    full_dirs_searched.append(canonical_dir)
                    follow.append(directory)

            except OSError:
                printD(f"Symlink loop: {directory}")
                continue

        # Get subfolder path
        subfolder = root[prefix_len:]
        subfolders.append(subfolder)

        # Update dirs parameter to prevent following recursive symlinks
        dirs[:] = follow

    return subfolders


def find_file_in_folders(folders:list, filename:str) -> str:
    """
    Searches a directory for a filename,

    return: filename:str or None
    """
    for folder in folders:
        for root, _, files in os.walk(folder, followlinks=True):
            if filename in files:
                # found file
                return os.path.join(root, filename)

    return None


# get relative path
def get_relative_path(item_path:str, parent_path:str) -> str:
    """
    Gets a relative path from an absolute path and its parent_path
    item path must start with parent_path
    return: relative_path:str
    """

    if not (item_path and parent_path):
        return ""

    if not item_path.startswith(parent_path):
        # return absolute path
        return item_path

    relative = item_path[len(parent_path):]
    if relative[:1] == "/" or relative[:1] == "\\":
        relative = relative[1:]

    # printD(f"relative: {relative}")
    return relative


# Allowed HTML tags
whitelist = re.compile(r"</?(a|img|br|p|b|strong|i|h[0-9]|code)[^>]*>")

# Allowed HTML attributes
attrs = re.compile(r"""(?:href|src|target)=['"]?[^\s'"]*['"]?""")

def safe_html_replace(match) -> str:
    """ Given a block of text, returns that block with most HTML removed
        and unneeded attributes pruned.
    """
    tag = None
    attr = None
    close = False

    match = whitelist.match(match.group(0))
    if match is not None:
        html_elem = match.group(0)
        tag = match.group(1)
        close = html_elem[1] == "/"
        if (tag in ["a", "img"]) and not close:
            sub_match = attrs.findall(html_elem)
            if sub_match is not None:
                attr = " ".join(sub_match)

        if close:
            return f"</{tag}>"

        return f"<{tag} {attr}>" if attr else f"<{tag}>"

    return ""

def safe_html(html:str) -> str:
    """ whitelist only HTML I"m comfortable displaying in webui """

    return re.sub("<[^<]+?>", safe_html_replace, html)


def trim_html(html:str) -> str:
    """ Remove any HTML for a given string and, if needed, replace it with
        a comparable plain-text alternative.
    """

    def sub_tag(match):
        tag = match.group(1)
        if tag == "/p":
            return "\n\n"
        if tag == "br":
            return "\n"
        if tag == "li":
            return "* "
        if tag in ["code", "/code"]:
            return "`"
        return ''

    def sub_escaped(match):
        escaped = match.group(1)
        unescaped = {
            "gt": ">",
            "lt": "<",
            "quot": '"',
            "amp": "&"
        }
        return unescaped.get(escaped, "")

    # non-breaking space. Useless unstyled content
    html = html.replace("\u00a0", "")

    # remove non-whitelisted HTML tags,
    # replace whitelisted tags with text-equivalents
    html = re.sub(r"<(/?[a-zA-Z]+)(?:[^>]+)?>", sub_tag, html)

    # Replace HTML-escaped characters with displayables.
    html = re.sub(r"\&(gt|lt|quot|amp)\;", sub_escaped, html)

    # Because we encapsulate the description in HTML comment,
    # We have to prevent those comments from being cancelled.
    html.replace("-->", "→")

    # https://github.com/AUTOMATIC1111/stable-diffusion-webui/pull/13241
    return f"<!--\n{html.strip()}\n-->"


def newer_version(ver1:str, ver2:str, allow_equal=False) -> bool:
    """ Returns ver1 > ver2
        if allow_equal, returns ver1 >= ver2
    """
    if allow_equal:
        return parse_version(ver1) >= parse_version(ver2)

    return parse_version(ver1) > parse_version(ver2)


def metadata_version(metadata:dict) -> str | bool:
    """ Attempts retrieve the extension version used to create
        to create the object block
    """
    try:
        return metadata["extensions"][SHORT_NAME]["version"]
    except KeyError:
        return False


def create_extension_block(data=None, skeleton=False) -> dict:
    """ Creates or edits an extensions block for usage in JSON files
        created or edited by this extension.

        Adds the current version of this extension to the extensions block
    """

    cur_time = ch_time()

    block = {
        SHORT_NAME: {
            "version": VERSION,
            "last_update": cur_time,
            "skeleton_file": skeleton
        }
    }

    if not data:
        return block

    data[SHORT_NAME] = block[SHORT_NAME]

    return data


filename_re = re.compile(r"[^A-Za-z\d\s\^\-\+_.\(\)\[\]]")
def bash_filename(filename:str) -> str:
    """
    Bashes a filename with a large fish until I'm comfortable using it.

    Keeps a limited set of valid characters, but does not account for
    reserved names like COM.
    """
    return re.sub(filename_re, "", filename)
