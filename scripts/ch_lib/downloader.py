""" -*- coding: UTF-8 -*-
Used for downloading files
"""
import os
#import sys
from tqdm import tqdm
import requests
import urllib3
from . import util

DL_EXT = ".downloading"

# disable ssl warning info
urllib3.disable_warnings()


def request_get(url, headers):
    """
    Performs a GET request
    return: request
    """
    try:
        request = requests.get(
            url,
            stream=True,
            verify=False,
            headers=headers,
            proxies=util.PROXIES,
            timeout=util.REQUEST_TIMEOUT
        )
    except TimeoutError:
        return None

    return request


def download_file(url, file_path, total_size):
    """
    Performs a file download.
    returns: True or an error message.
    """
    # use a temp file for downloading
    dl_file_path = f"{file_path}{DL_EXT}"

    util.printD(f"Downloading to temp file: {dl_file_path}")

    # check if downloading file exists
    downloaded_size = 0
    if os.path.exists(dl_file_path):
        downloaded_size = os.path.getsize(dl_file_path)
        util.printD(f"Resuming partially downloaded file from progress: {downloaded_size}")

    # create header range
    headers = {
        "Range": f"bytes={downloaded_size:d}-",
        "User-Agent": util.def_headers['User-Agent']
    }

    # download with header
    request = request_get(
        url,
        headers,
    )

    # write to file
    with open(dl_file_path, 'wb') as dl_file, tqdm(
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024
    ) as progress_bar:

        for chunk in request.iter_content(chunk_size=1024):
            if chunk:
                downloaded_size = dl_file.write(chunk)
                # write to disk
                dl_file.flush()
                progress_bar.update(downloaded_size)

    # check file size
    downloaded_size = os.path.getsize(dl_file_path)
    if downloaded_size < total_size:
        return util.indented_msg(
            f"""
            File is not the correct size.
            Expected {total_size:d}, got {downloaded_size:d}.
            Try again later or download it manually: {url}
            """
        )

    # rename file
    os.rename(dl_file_path, file_path)
    util.printD(f"File Downloaded to: {file_path}")
    return True


def get_file_path_from_headers(headers, folder):
    """
    Parses a request header to get a filename
    then builds a file_path.

    return: file_path:str
    """

    content_disposition = headers.headers.get("Content-Disposition", None)

    if content_disposition is None:
        util.printD("Can not get file name from download url's header")
        return None

    # Extract the filename from the header
    # content of a CD: "attachment;filename=FileName.txt"
    # in case "" is in CD filename's start and end, need to strip them out
    filename = content_disposition.split("=")[1].strip('"')
    filename = filename.encode('iso8859-1').decode('utf-8')
    if not filename:
        util.printD(f"Fail to get file name from Content-Disposition: {content_disposition}")
        return None

    # with folder and filename, now we have the full file path
    return os.path.join(folder, filename)


# output is downloaded file path
def dl(url, folder, filename, file_path, duplicate=None):
    """
    Perform a download.

    returns: tuple(success, filepath or failure message)
    """

    request_headers = request_get(
        url,
        headers=util.def_headers
    )

    util.printD(f"Start downloading from: {url}")

    # get file_path
    if not file_path:
        if not (folder or os.path.isdir(folder)):
            return (
                False,
                "No directory to save model to."
            )

        if filename:
            file_path = os.path.join(folder, filename)
        else:
            file_path = get_file_path_from_headers(request_headers, folder)

        if file_path is None:
            return (
                False,
                "Could not get a file_path to place saved file."
            )

    util.printD(f"Target file path: {file_path}")
    base, ext = os.path.splitext(file_path)

    # duplicate handling
    if os.path.isfile(file_path):
        if duplicate == "Rename New":
            # check if file is already exist
            count = 2
            new_base = base
            while os.path.isfile(file_path):
                util.printD("Target file already exist.")
                # re-name
                new_base = f"{base}_{count}"
                file_path = f"{new_base}{ext}"
                count += 1

        elif duplicate != "Overwrite":
            return (
                False,
                f"File {file_path} already exists! Download will not proceed."
            )

    # get file size
    total_size = int(request_headers.headers['Content-Length'])
    util.printD(f"File size: {total_size}")

    download_file(url, file_path, total_size)

    return (True, file_path)
