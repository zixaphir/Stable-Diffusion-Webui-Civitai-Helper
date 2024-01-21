""" -*- coding: UTF-8 -*-
Used for downloading files
"""
from __future__ import annotations
from collections.abc import Generator
import os
import platform
import time
from typing import cast, Literal
from tqdm import tqdm
import requests
import urllib3
from . import util


DL_EXT = ".downloading"
MAX_RETRIES = 30

# disable ssl warning info
urllib3.disable_warnings()

# hard-coded for now, could further expand to make it customizeable
def calculate_stepback_delay_seconds(
    retries: int
) -> int:
    if retries == 0:
        return 0
    elif retries < 5:
        return 5
    elif retries < 10:
        return 10
    elif retries < 15:
        return 30
    elif retries < 20:
        return 60
    else:
        return 180


def request_get(
    url:str,
    headers:dict | None=None,
    retries=0
) -> tuple[Literal[True], requests.Response] | tuple[Literal[False], str]:
    """
    Performs a GET request

    returns: tuple(success:bool, response:Response or failure message:str)
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
            retry_delay = calculate_stepback_delay_seconds(retries)
            util.printD(f"Retrying after {retry_delay} seconds")

            # Step-back delay to allow for website to recover
            time.sleep(retry_delay)

            # recursive retry
            return request_get(
                url,
                headers,
                retries + 1
            )

        return (False, reason)

    return (True, response)


def visualize_progress(percent:int, downloaded:int, total:int, speed:int | float, show_bar=True) -> str:
    """ Used to display progress in webui """

    s_total = f"{total}"
    s_downloaded = f"{downloaded:>{len(s_total)}}"
    s_percent = f"{percent:>3}"
    s_speed = f'{human_readable_filesize(speed)}Bps'

    snippet = f"`{s_percent}%: {s_downloaded} / {s_total} @ {s_speed}`"

    if not show_bar:
        # Unfortunately showing a progress bar in webui
        # is very weird on mobile with limited horizontal
        # space
        return snippet.replace(" ", "\u00a0")

    progress = "\u2588" * percent

    return f"`[{progress:<100}] {snippet}`".replace(" ", "\u00a0")


def download_progress(
    url:str,
    file_path:str,
    total_size:int,
    headers:dict | None=None,
    response_without_range:requests.Response | None=None
) -> Generator[tuple[bool, str] | str, None, None]:
    """
    Performs a file download.

    yields: tuple(success:bool, filepath or failure message:str) or progress:str
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

    # use response without range or create request with range
    if response_without_range and downloaded_size == 0:
        response = response_without_range
    else:
        if response_without_range:
            response_without_range.close()

        # create header range
        headers_with_range = util.append_default_headers({
            **headers,
            "Range": f"bytes={downloaded_size:d}-",
        })

        # download with header
        try:
            success, response_or_error = request_get(
                url,
                headers=headers_with_range,
            )

        except requests.HTTPError as dl_error:
            # 416 - Range Not Satisfiable
            response = dl_error.response
            if not response or response.status_code != 416:
                raise

            util.printD("Could not resume download from existing temporary file. Restarting download")

            os.remove(dl_path)

            yield from download_progress(url, file_path, total_size, headers)
            return

        if not success:
            yield (False, cast(str, response_or_error))
            return

        response = cast(requests.Response, response_or_error)

    last_tick = 0
    start = time.time()

    downloaded_this_session = 0

    # write to file
    with open(dl_path, 'ab') as target, tqdm(
        initial=target.tell(),
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


def get_file_path_from_service_headers(response:requests.Response, folder:str) -> str | None:
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
    folder:str | None=None,
    filename:str | None=None,
    file_path:str | None=None,
    headers:dict | None=None,
    duplicate:str | None=None
) -> Generator[tuple[bool, str] | str, None, None]:
    """
    Perform a download.

    yields: tuple(success:bool, filepath or failure message:str) or progress:str
    """

    if not headers:
        headers = {}

    success, response_or_error = request_get(url, headers=headers)

    if not success:
        yield (False, cast(str, response_or_error))
        return

    response = cast(requests.Response, response_or_error)

    util.printD(f"Start downloading from: {url}")

    # close the response when the function ends
    with response:

        # get file_path
        if not file_path:
            if not (folder and os.path.isdir(folder)):
                yield (
                    False,
                    "No directory to save model to."
                )
                return

            if filename:
                file_path = os.path.join(folder, filename)
            else:
                file_path = get_file_path_from_service_headers(response, folder)

            if not file_path:
                yield (
                    False,
                    "Could not get a file_path to place saved file."
                )
                return

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
                return

        # get file size
        total_size = int(response.headers['Content-Length'])
        util.printD(f"File size: {total_size} ({human_readable_filesize(total_size)})")

        yield from download_progress(url, file_path, total_size, headers, response)


def human_readable_filesize(size:int | float) -> str:
    """ Convert file size to human readable text """
    prefixes = ["", "K", "M", "G"]

    # Mac reports filesizes in multiples of 1000
    # We should respect platform differences
    unit = 1000 if platform.system() == "Darwin" else 1024

    i = 0
    while size > unit and i < len(prefixes) - 1:
        i += 1
        size = size / unit

    return f"{round(size, 2)}{prefixes[i]}"


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
