""" -*- coding: UTF-8 -*-
Used for downloading files
"""
from __future__ import annotations
import os
import time
from tqdm import tqdm
import requests
import urllib3
from . import util


DL_EXT = ".downloading"
MAX_RETRIES = 3

# disable ssl warning info
urllib3.disable_warnings()


def request_get(url:str, headers=None, retries=0) -> tuple[bool, requests.Response]:
    """
    Performs a GET request
    return: request
    """

    headers = util.append_default_headers(headers or {})

    try:
        response = requests.get(
            url,
            stream=True,
            verify=False,
            headers=headers,
            proxies=util.PROXIES,
            timeout=util.REQUEST_TIMEOUT
        )

    except TimeoutError:
        print(f"GET Request timed out for {url}")
        return (False, None)

    if not response.ok:
        code = response.status_code
        reason = response.reason
        util.printD(util.indented_msg(
            f"""
            GET Request failed with error code:
            {code}: {reason}
            """
        ))
        if response.status_code != 404 and retries < MAX_RETRIES:
            util.printD("Retrying")
            return request_get(url, headers, retries + 1)

        return (False, response)

    return (True, response)


def alt_progressbar(percent:int) -> str:
    """ Mostly used to display a progress bar in webui """

    percent_as_int = int(percent)
    progress = "\u2588" * percent_as_int
    remaining = "\u00a0" * (100 - percent_as_int)

    return f"`[{progress}{remaining}] {percent}%`"


def download_progress(url:str, file_path:str, total_size:int) -> bool | float:
    """
    Performs a file download.
    returns: True or an error message.
    """
    # use a temp file for downloading
    dl_path = f"{file_path}{DL_EXT}"

    util.printD(f"Downloading to temp file: {dl_path}")

    # check if downloading file exists
    downloaded_size = 0
    if os.path.exists(dl_path):
        downloaded_size = os.path.getsize(dl_path)
        util.printD(f"Resuming partially downloaded file from progress: {downloaded_size}")

    # create header range
    headers = {
        "Range": f"bytes={downloaded_size:d}-"
    }

    # download with header
    success, response = request_get(
        url,
        headers=headers,
    )

    if not success:
        return (False, "Could not get request headers.")

    last_tick = 0
    # write to file
    with open(dl_path, 'wb') as target, tqdm(
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=256*1024):
            if chunk:
                downloaded_size += len(chunk)
                written = target.write(chunk)

                # write to disk
                target.flush()

                progress_bar.update(written)

                percent = 100 * (downloaded_size / total_size)
                timer = time.time()
                if timer - last_tick > 0.2 or int(percent) == 100:
                    # Gradio output is a *slooowwwwwwww* asynchronous FIFO queue
                    last_tick = timer
                    alt_bar = alt_progressbar(
                        round(
                            percent,
                            2
                        )
                    )
                    yield alt_bar

    # check file size
    downloaded_size = os.path.getsize(dl_path)
    if downloaded_size < total_size:
        return util.indented_msg(
            f"""
            File is not the correct size.
            Expected {total_size:d}, got {downloaded_size:d}.
            Try again later or download it manually: {url}
            """
        )

    # rename file
    os.rename(dl_path, file_path)
    output = f"File Downloaded to: {file_path}"
    util.printD(output)
    yield (True, output)


def get_file_path_from_service_headers(response:requests.Response, folder:str) -> str:
    """
    Parses a response header to get a filename
    then builds a file_path.

    return: file_path:str
    """

    content_disposition = response.headers.get("Content-Disposition", None)

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
def dl_file(
    url:str,
    folder=None,
    filename=None,
    file_path=None,
    duplicate=None
) -> tuple[bool, str]:
    """
    Perform a download.

    returns: tuple(success:bool, filepath or failure message:str)
    """

    success, response = request_get(url)

    if not success:
        return (False, f"Failed to get file download headers for {url}")

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
            file_path = get_file_path_from_service_headers(response, folder)

        if not file_path:
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
                # rename duplicate
                new_base = f"{base}_{count}"
                file_path = f"{new_base}{ext}"
                count += 1

        elif duplicate != "Overwrite":
            return (
                False,
                f"File {file_path} already exists! Download will not proceed."
            )

    # get file size
    total_size = int(response.headers['Content-Length'])
    util.printD(f"File size: {total_size}")

    for result in download_progress(url, file_path, total_size):
        if isinstance(result, str):
            yield result
            continue

    util.printD("Did we make it?")

    yield (True, file_path)


def error(download_url:str, msg:str) -> str:
    """ Display a download error """
    output = util.indented_msg(
        f"""
        Download failed.
        {msg}
        Download url: {download_url}
        """
    )
    util.printD(output)
    return output
