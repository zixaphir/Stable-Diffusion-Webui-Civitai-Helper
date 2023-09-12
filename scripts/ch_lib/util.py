# -*- coding: UTF-8 -*-
import os
import sys
import io
import re
import hashlib
import requests
import shutil


short_name = "sd_civitai_helper"
version = "1.7.0"

def_headers = {'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'}


proxies = None


# print for debugging
def printD(msg):
    print(f"Civitai Helper: {msg}", file=sys.stderr)


def read_chunks(file, size=io.DEFAULT_BUFFER_SIZE):
    """Yield pieces of data from a file-like object until EOF."""
    while True:
        chunk = file.read(size)
        if not chunk:
            break
        yield chunk

# Now, hashing use the same way as pip's source code.
def gen_file_sha256(filname):
    printD("Use Memory Optimized SHA256")
    blocksize=1 << 20
    h = hashlib.sha256()
    length = 0
    with open(os.path.realpath(filname), 'rb') as f:
        for block in read_chunks(f, size=blocksize):
            length += len(block)
            h.update(block)

    hash_value =  h.hexdigest()
    printD(f"sha256: {hash_value}")
    printD(f"length: {length}")
    return hash_value


# get preview image
def download_file(url, path):
    printD(f"Downloading file from: {url}")
    # get file
    r = requests.get(url, stream=True, headers=def_headers, proxies=proxies)
    if not r.ok:
        printD(f"Get error code: {r.status_code}")
        printD(r.text)
        return

    # write to file
    with open(os.path.realpath(path), 'wb') as f:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, f)

    printD(f"File downloaded to: {path}")


# get subfolder list
def get_subfolders(folder:str) -> list:
    printD(f"Get subfolder for: {folder}")
    if not folder:
        printD("folder can not be None")
        return

    if not os.path.isdir(folder):
        printD("path is not a folder")
        return

    prefix_len = len(folder)
    subfolders = []
    for root, dirs, files in os.walk(folder, followlinks=True):
        for dir in dirs:
            full_dir_path = os.path.join(root, dir)
            # get subfolder path from it
            subfolder = full_dir_path[prefix_len:]
            subfolders.append(subfolder)

    return subfolders


# get relative path
def get_relative_path(item_path:str, parent_path:str) -> str:
    # printD(f"item_path: {item_path}")
    # printD(f"parent_path: {parent_path}")
    # item path must start with parent_path
    if not item_path:
        return ""
    if not parent_path:
        return ""
    if not item_path.startswith(parent_path):
        return item_path

    relative = item_path[len(parent_path):]
    if relative[:1] == "/" or relative[:1] == "\\":
        relative = relative[1:]

    # printD(f"relative: {relative}")
    return relative


whitelist = re.compile(r"</?(a|img|br|p|b|strong|i|h[0-9]|code)[^>]*>")
attrs = re.compile(r"""(?:href|src|target)=['"]?[^\s'"]*['"]?""")

def safe_html_replace(match):
    tag = None
    attr = None
    close = False

    m = whitelist.match(match.group(0))
    if m is not None:
        el = m.group(0)
        tag = m.group(1)
        close = el[1] == "/"
        if (tag in ["a", "img"]) and not close:
            m2 = attrs.findall(el)
            if m2 is not None:
                attr = " ".join(m2)

        if close:
            return f"</{tag}>"
        else:
            return f"<{tag} {attr}>" if attr else f"<{tag}>"

    return ""

def safe_html(s):
    """ whitelist only HTML I"m comfortable displaying in webui """

    return re.sub("<[^<]+?>", safe_html_replace, s)


def trim_html(s):
    """ Remove any HTML for a given string and, if needed, replace it with
        a comparable plain-text alternative.
    """

    def sub_tag(m):
        tag = m.group(1)
        if tag == "/p":
            return "\n\n"
        if tag == "br":
            return "\n"
        if tag == "li":
            return "* "
        if tag in ["code", "/code"]:
            return "`"
        return ''

    def sub_escaped(m):
        escaped = m.group(1)
        unescaped = {
            "gt": ">",
            "lt": "<",
            "quot": '"',
            "amp": "&"
        }
        return unescaped.get(escaped, "")

    s = re.sub(r"<(/?[a-zA-Z]+)(?:[^>]+)?>", sub_tag, s)
    s = re.sub(r"\&(gt|lt|quot|amp)\;", sub_escaped, s)

    return s
