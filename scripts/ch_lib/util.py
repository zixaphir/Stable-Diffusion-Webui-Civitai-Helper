""" -*- coding: UTF-8 -*-
Utility functions for Stable Diffusion Civitai Helper
"""
import os
import sys
import io
import re
import hashlib
import shutil
import requests
import gradio as gr
import launch
from packaging.version import parse as parse_version

# used to append extension information to JSON/INFO files
SHORT_NAME = "sd_civitai_helper"

# current version of the exension
VERSION = "1.7.3"

# Civitai INFO files below this version will regenerated
COMPAT_VERSION_CIVITAI = "1.7.2"

# SD webui model info JSON below this version will be regenerated
COMPAT_VERSION_SDWEBUI = "1.7.2"

def_headers = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
}

proxies = None

# print for debugging
def printD(msg):
    """ Print a message to stderr """
    print(f"Civitai Helper: {msg}", file=sys.stderr)

def info(msg):
    """ Display an info smessage on the client DOM """
    gr.Info(msg)

def warning(msg):
    """ Display a warning message on the client DOM """
    gr.Warning(msg)

def error(msg):
    """ Display an error message on the client DOM """
    gr.Error(msg)

def download_error(download_url, msg):
    """ Display a download error """
    output = f"Download failed, check console log for detail. Download url: {download_url}"
    printD(output)
    printD(msg)
    return output


def read_chunks(file, size=io.DEFAULT_BUFFER_SIZE):
    """Yield pieces of data from a file-like object until EOF."""
    while True:
        chunk = file.read(size)
        if not chunk:
            break
        yield chunk

def gen_file_sha256(filname):
    """ pip-style sha256 hash generation"""
    printD("Use Memory Optimized SHA256")
    blocksize=1 << 20
    sha256_hash = hashlib.sha256()
    length = 0
    with open(os.path.realpath(filname), 'rb') as read_file:
        for block in read_chunks(read_file, size=blocksize):
            length += len(block)
            sha256_hash.update(block)

    hash_value =  sha256_hash.hexdigest()
    printD(f"sha256: {hash_value}")
    printD(f"length: {length}")
    return hash_value


def download_file(url, path):
    """ Download a preview image """

    printD(f"Downloading file from: {url}")

    # get file
    request = requests.get(
        url,
        stream=True,
        headers=def_headers,
        proxies=proxies,
        timeout=10
    )

    if not request.ok:
        printD(f"Get error code: {request.status_code}")
        printD(request.text)
        return

    # write to file
    with open(os.path.realpath(path), 'wb') as writefile:
        request.raw.decode_content = True
        shutil.copyfileobj(request.raw, writefile)

    printD(f"File downloaded to: {path}")


def get_subfolders(folder:str) -> list:
    """ return: list of subfolders """
    printD(f"Get subfolder for: {folder}")
    if not folder:
        printD("folder can not be None")
        return None

    if not os.path.isdir(folder):
        printD("path is not a folder")
        return None

    prefix_len = len(folder)
    subfolders = []
    for root, dirs, _ in os.walk(folder, followlinks=True):
        for directory in dirs:
            full_dir_path = os.path.join(root, directory)
            # get subfolder path from it
            subfolder = full_dir_path[prefix_len:]
            subfolders.append(subfolder)

    return subfolders


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

def safe_html_replace(match):
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

def safe_html(html):
    """ whitelist only HTML I"m comfortable displaying in webui """

    return re.sub("<[^<]+?>", safe_html_replace, html)


def trim_html(html):
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

    # https://github.com/AUTOMATIC1111/stable-diffusion-webui/pull/13241
    return f"<!--\n{html.strip()}\n-->"


def newer_version(ver1, ver2, allow_equal=False):
    """ Returns ver1 > ver2
        if allow_equal, returns ver1 >= ver2
    """
    if allow_equal:
        return parse_version(ver1) >= parse_version(ver2)

    return parse_version(ver1) > parse_version(ver2)


def metadata_version(metadata):
    """ Attempts retrieve the extension version used to create
        to create the object block
    """
    try:
        return metadata["extensions"][SHORT_NAME]["version"]
    except KeyError:
        return False


def create_extension_block(data=None):
    """ Creates or edits an extensions block for usage in JSON files
        created or edited by this extension.

        Adds the current version of this extension to the extensions block
    """
    block = {
        SHORT_NAME: {
            "version": VERSION
        }
    }

    if not data:
        return block

    if not data.get(SHORT_NAME, False):
        data[SHORT_NAME] = block[SHORT_NAME]
        return data

    data[SHORT_NAME]["version"] = VERSION

    return data


def webui_version():
    ''' Gets the current webui version using webui's launch tools

        The version is expected to be in the format `v1.6.0-128-g792589fd`,
        tho all that is explicitly required is `vX`.

        returns the version in the form 'X.Y.Z'
    '''
    version = None
    tag = launch.git_tag()
    match = re.match(r"v([\d.]+)", tag)
    if match:
        version = match.group(1)
    return version
