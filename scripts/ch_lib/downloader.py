# -*- coding: UTF-8 -*-
import sys
import requests
import os
from . import util


DL_EXT = ".downloading"

# disable ssl warning info
requests.packages.urllib3.disable_warnings()

# output is downloaded file path
def dl(url, folder, filename, filepath, duplicate=None):
    util.printD(f"Start downloading from: {url}")
    # get file_path
    file_path = ""
    if filepath:
        file_path = filepath
    else:
        # if file_path is not in parameter, then folder must be in parameter
        if not folder:
            output = "Folder is none"
            util.printD(output)
            return (False, output)

        if not os.path.isdir(folder):
            output = f"Folder does not exist: {folder}"
            util.printD(output)
            return (False, output)

        if filename:
            file_path = os.path.join(folder, filename)

    # first request for header
    rh = requests.get(url, stream=True, verify=False, headers=util.def_headers, proxies=util.proxies)
    # get file size
    total_size = 0
    total_size = int(rh.headers['Content-Length'])
    util.printD(f"File size: {total_size}")

    # if file_path is empty, need to get file name from download url's header
    if not file_path:
        filename = ""
        if "Content-Disposition" in rh.headers.keys():
            cd = rh.headers["Content-Disposition"]
            # Extract the filename from the header
            # content of a CD: "attachment;filename=FileName.txt"
            # in case "" is in CD filename's start and end, need to strip them out
            filename = cd.split("=")[1].strip('"')
            filename = filename.encode('iso8859-1').decode('utf-8')
            if not filename:
                return (False, f"Fail to get file name from Content-Disposition: {cd}")

        if not filename:
            return (False, "Can not get file name from download url's header")

        # with folder and filename, now we have the full file path
        file_path = os.path.join(folder, filename)


    util.printD(f"Target file path: {file_path}")
    base, ext = os.path.splitext(file_path)

    # duplicate handling
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
        if os.path.isfile(file_path):
            return (False, "File already exists! Download will not proceed.")

    # use a temp file for downloading
    dl_file_path = f"{file_path}{DL_EXT}"

    util.printD(f"Downloading to temp file: {dl_file_path}")

    # check if downloading file exists
    downloaded_size = 0
    if os.path.exists(dl_file_path):
        downloaded_size = os.path.getsize(dl_file_path)

    util.printD(f"Downloaded size: {downloaded_size}")

    # create header range
    headers = {'Range': 'bytes=%d-' % downloaded_size}
    headers['User-Agent'] = util.def_headers['User-Agent']

    # download with header
    r = requests.get(url, stream=True, verify=False, headers=headers, proxies=util.proxies)

    # write to file
    with open(dl_file_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                downloaded_size += len(chunk)
                f.write(chunk)
                # force to write to disk
                f.flush()

                # progress
                progress = int(50 * downloaded_size / total_size)
                sys.stdout.reconfigure(encoding='utf-8')
                sys.stdout.write("\r[%s%s] %d%%" % ('-' * progress, ' ' * (50 - progress), 100 * downloaded_size / total_size))
                sys.stdout.flush()

    print()

    # rename file
    os.rename(dl_file_path, file_path)
    util.printD(f"File Downloaded to: {file_path}")
    return (True, file_path)

