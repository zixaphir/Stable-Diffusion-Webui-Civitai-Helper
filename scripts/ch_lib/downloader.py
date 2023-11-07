""" -*- coding: UTF-8 -*-
Used for downloading files
"""
from __future__ import annotations
import os
import platform
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
        output = f"GET Request timed out for {url}"
        print(output)
        return (False, output)

    if not response.ok:
        status_code = response.status_code
        reason = response.reason
        util.printD(util.indented_msg(
            f"""
            GET Request failed with error code:
            {status_code}: {reason}
            """
        ))

        if status_code == 401:
            return (
                False,
                "This download requires Authentication. Please add an API Key to Civitai Helper's settings to continue this download. See [Wiki](https://github.com/zixaphir/Stable-Diffusion-Webui-Civitai-Helper/wiki/Civitai-API-Key) for details on how to create an API Key."
            )

        if status_code == 416:
            response.raise_for_status()

        if status_code != 404 and retries < MAX_RETRIES:
            util.printD("Retrying")
            return request_get(url, headers, retries + 1)

        return (False, response)

    return (True, response)


def visualize_progress(percent:int, downloaded, total, speed, show_bar=True) -> str:
    """ Used to display progress in webui """

    percent_as_int = percent
    total = f"{total}"
    downloaded = f"{downloaded:>{len(total)}}"
    percent = f"{percent:>3}"

    snippet = f"`{percent}%: {downloaded} / {total} @ {speed}`"

    if not show_bar:
        # Unfortunately showing a progress bar in webui
        # is very weird on mobile with limited horizontal
        # space
        return snippet.replace(" ", "\u00a0")

    progress = "\u2588" * percent_as_int

    return f"`[{progress:<100}] {snippet}`".replace(" ", "\u00a0")


def download_progress(url:str, file_path:str, total_size:int, headers=None) -> bool | float:
    """
    Performs a file download.
    returns: True or an error message.
    """
    # use a temp file for downloading

    if not headers:
        headers = {}

    dl_path = f"{file_path}{DL_EXT}"

    util.printD(f"Downloading to temp file: {dl_path}")

    # check if downloading file exists
    downloaded_size = 0
    if os.path.exists(dl_path):
        downloaded_size = os.path.getsize(dl_path)
        util.printD(f"Resuming partially downloaded file from progress: {downloaded_size}")

    # create header range
    headers["Range"] = f"bytes={downloaded_size:d}-"
    headers = util.append_default_headers(headers)

    # download with header
    try:
        success, response = request_get(
            url,
            headers=headers,
        )

    except requests.HTTPError as dl_error:
        # 416 - Range Not Satisfiable
        response = dl_error.response
        if response.status_code != 416:
            raise

        util.printD("Could not resume download from existing temporary file. Restarting download")

        os.remove(dl_path)

        for result in download_progress(url, file_path, total_size, headers):
            yield result

    if not success:
        yield (False, response)

    last_tick = 0
    start = time.time()

    downloaded_this_session = 0

    # write to file
    with open(dl_path, 'wb') as target, tqdm(
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=256*1024):
            if chunk:
                downloaded_this_session += len(chunk)
                downloaded_size += len(chunk)
                written = target.write(chunk)

                # write to disk
                target.flush()

                progress_bar.update(written)

                percent = int(100 * (downloaded_size / total_size))
                timer = time.time()

                # Gradio output is a *slooowwwwwwww* asynchronous FIFO queue
                if timer - last_tick > 0.2 or percent == 100:

                    last_tick = timer
                    elapsed = timer - start
                    speed = downloaded_this_session // elapsed if elapsed >= 1 \
                        else downloaded_this_session

                    # Mac reports filesizes in multiples of 1000
                    # We should respect platform differences
                    unit = 1000 if platform.system() == "Darwin" else 1024

                    i = 0
                    while speed > unit:
                        i += 1
                        speed = speed / unit
                        if i >= 3:
                            break

                    speed = f'{round(speed, 2)}{["", "K", "M", "G"][i]}Bps'

                    text_progress = visualize_progress(
                        percent,
                        downloaded_size,
                        total_size,
                        speed,
                        False
                    )

                    yield text_progress

    # check file size
    downloaded_size = os.path.getsize(dl_path)
    if downloaded_size != total_size:
        warning = util.indented_msg(
            f"""
            File is not the correct size: {file_path}.
            Expected {total_size:d}, got {downloaded_size:d}.
            The file may be corrupt. If you encounter issues,
            you can try again later or download the file manually: {url}
            """
        )
        util.warning(warning)
        util.printD(warning)

    # rename file
    os.rename(dl_path, file_path)
    output = f"File Downloaded to: {file_path}"
    util.printD(output)

    yield (True, file_path)


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
    headers=None,
    duplicate=None
) -> tuple[bool, str]:
    """
    Perform a download.

    returns: tuple(success:bool, filepath or failure message:str)
    """

    if not headers:
        headers = {}

    success, response = request_get(url, headers=headers)

    if not success:
        yield (False, response)

    response.close()

    util.printD(f"Start downloading from: {url}")

    # get file_path
    if not file_path:
        if not (folder and os.path.isdir(folder)):
            yield (
                False,
                "No directory to save model to."
            )

        if filename:
            file_path = os.path.join(folder, filename)
        else:
            file_path = get_file_path_from_service_headers(response, folder)

        if not file_path:
            yield (
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
            yield (
                False,
                f"File {file_path} already exists! Download will not proceed."
            )

    # get file size
    total_size = int(response.headers['Content-Length'])
    util.printD(f"File size: {total_size}")

    for result in download_progress(url, file_path, total_size, headers):
        if not isinstance(result, str):
            success, output = result
            break

        yield result

    yield (success, output)


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
