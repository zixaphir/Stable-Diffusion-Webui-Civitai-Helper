""" -*- coding: UTF-8 -*-
Check for duplicate models.
"""

import os
import html
import json
import traceback
from . import util
from . import model
from . import civitai
from . import templates


def scan_for_dups(scan_model_types, cached_hash):
    """ Scans model metadata to detect duplicates
        by using the model hash.
    """

    util.printD("Start scan_for_dups")
    output = ""

    # check model types
    if not scan_model_types:
        output = "Model Types is None. Will not scan."
        util.printD(output)
        return output

    model_types = []

    # check type if it is a string
    if isinstance(scan_model_types, str):
        model_types.append(scan_model_types)
    else:
        model_types = scan_model_types

    models = gather_model_data(model_types, cached_hash)
    dups = check_for_dups(models)

    output = create_dups_html(dups)

    return f"<section class=extra-network-cards>{output}</section>"


def gather_model_data(model_types, cached_hash):
    """ Collects model metadata files and parses them for metadata """

    models = {}

    for model_type, model_folder in model.folders.items():
        if model_type not in model_types:
            continue

        models[model_type] = scan_dir(model_folder, model_type, cached_hash)

    return models

def scan_dir(model_folder, model_type, cached_hash):
    """
        Scans dir for models and their metadata
    """

    suffix = f"{civitai.SUFFIX}{model.CIVITAI_EXT}"
    suffix_len = -len(suffix)

    metadata = []
    util.printD(f"Scanning path: {model_folder}")
    for root, _, files in os.walk(model_folder, followlinks=True):
        for filename in files:
            try:
                if filename[suffix_len:] == suffix:
                    data = parse_metadata(model_folder, root, filename, suffix, model_type, cached_hash)
                    if data:
                        metadata.append(data)

            except (IndexError, KeyError, ValueError):
                util.printD(f"Error occurred on file `{root}/{filename}`")
                traceback.print_exc()
                util.printD("You can probably ignore this")
                continue

    return metadata


def parse_metadata(model_folder, root, filename, suffix, model_type, cached_hash):
    """ Parses model JSON file for hash / other metadata """

    metadata = {}

    filepath = f"{root}/{filename}"
    model_name = filename[:-len(suffix)]

    util.printD(f"Processing {model_name}")

    with open(filepath) as file:
        try:
            model_info = json.load(file)
        except json.JSONDecodeError:
            return None

    model_file = model_info["files"][0]
    model_ext = model_file["name"].split(".").pop()

    description = None

    # Backwards compatibility with older model info files
    # from pre civitai helper 1.7
    try:
        description = model_info["model"]["description"]
    except (ValueError, KeyError):
        description = model_info.get("description", None)

    if not description:
        description = ""

    model_path = f"{root}/{model_name}.{model_ext}"

    if not os.path.isfile(model_path):
        model_path = locate_model_from_partial(root, model_name)

        if not (model_path and os.path.isfile(model_path)):
            util.printD(f"No model path found for {filepath}")
            return None

    sha256 = get_hash(model_path, model_file, model_type, cached_hash)


    metadata = {
        "model_name": model_name,
        "civitai_name": model_info["model"]["name"],
        "description": description,
        "model_path": model_path,
        "subpath": model_path[len(model_folder):],
        "model_type": model_type,
        "hash": sha256,
        "search_term": make_search_term(model_type, model_path, sha256)
    }

    return metadata


def get_hash(model_path, model_file, model_type, cached_hash):
    """
        Get or calculate hash of `model_path/model_file`
    """

    sha256 = None
    if cached_hash:
        try:
            sha256 = model_file["hashes"]["SHA256"].upper()

        except (KeyError, ValueError):
            pass

        if sha256:
            return sha256

        util.printD(f"No sha256 hash in metadata for {model_file}. \
                \n\tGenerating one. This will be slower")

    model_hash_type = {
        "ckp": "checkpoint",
        "ti": "textual_inversion",
        "hyper": "hypernet",
        "lora": "lora",
        "lycoris": "lycoris"
    }[model_type]

    sha256 = util.gen_file_sha256(
        model_path,
        model_type=model_hash_type,
        use_addnet_hash=False
    ).upper()

    return sha256


def make_search_term(model_type, model_path, sha256):
    """ format search term for the correct model type """

    folder = model.folders[model_type]
    subpath = model_path[len(folder):]
    sha256 = sha256.lower()

    if not subpath.startswith("/"):
        subpath = f"/{subpath}"

    if model_type == "hyper":
        snippet = subpath.split(".")
        snippet.pop()
        subpath = ".".join(snippet)
        return f"{subpath}"

    # All other supported model types seem to use this format
    return f"{subpath} {sha256}"


def locate_model_from_partial(root, model_name):
    """
        Tries to locate a model if the extension
        doesn't match the metadata
    """

    for ext in model.EXTS:
        filename = f"{root}/{model_name}{ext}"
        if os.path.isfile(filename):
            return filename

    return None


def check_for_dups(models):
    """
        returns all models that share the a stored
        sha256 hash with another model
    """

    scanned = {}
    dups = {}

    for model_type, models_of_type in models.items():
        scanned[model_type] = {}
        scanned_type = scanned[model_type]
        for model_data in models_of_type:
            sha256 = model_data["hash"]

            if model_type == "lycoris":
                if is_lycoris_lora(model_data, scanned):
                    continue

            if not scanned_type.get(sha256, None):
                scanned_type[sha256] = [model_data]
                continue

            scanned_type[sha256].append(model_data)

    for model_type, models_of_type in scanned.items():
        dups_of_type = dups[model_type] = {}
        for key, model_data in models_of_type.items():
            if len(model_data) > 1:
                dups_of_type[key] = model_data

    return dups


def get_preview(model_path):
    """ Finds the appropriate preview image for a model """

    prevs = model.get_potential_model_preview_files(model_path, True)

    bg_image = None
    for prev in prevs:
        if os.path.isfile(prev):
            bg_image = prev
            break

    if not bg_image:
        return ""

    return templates.duplicate_preview.substitute(
        bg_image=bg_image
    )


def make_model_card(model_data):
    """ Creates the HTML for a single model card """

    card_t = templates.duplicate_card

    bg_image = get_preview(model_data["model_path"])
    style = "font-size:100%"
    model_name = model_data["model_name"]
    subpath = model_data["subpath"]
    description = html.escape(model_data["description"])
    search_term = model_data["search_term"]
    model_type = model_data["model_type"]

    card = card_t.substitute(
        style=style,
        name=model_name,
        path=subpath,
        background_image=bg_image,
        description=description,
        search_term=search_term,
        model_type=model_type
    )

    return card


def create_dups_html(dups):
    """ creates an HTML snippet containing duplicate models """

    article_t = templates.duplicate_article
    row_t = templates.duplicate_row
    column_t = templates.duplicate_column

    articles = []

    for model_type, models_of_type in dups.items():
        rows = []
        for dup_data in models_of_type.values():
            civitai_name = ""
            sha256 = ""

            columns = []
            for count, model_data in enumerate(dup_data):
                card = make_model_card(model_data)

                column = column_t.substitute(
                    count=count,
                    card=card
                )

                columns.append(column)

                if model_data["civitai_name"] and not civitai_name:
                    civitai_name = model_data["civitai_name"]
                    sha256 = model_data["hash"]

            rows.append(
                row_t.substitute(
                    civitai_name=civitai_name,
                    hash=sha256,
                    columns="".join(columns)
                )
            )

        content = ""
        if len(rows) > 0:
            content = "".join(rows)
        else:
            content = f"No duplicate {model_type}s found!"

        articles.append(
            article_t.substitute(
                section_name=model_type,
                contents=content
            )
        )

    if len(articles) < 1:
        return "Found no duplicate models!"

    return "".join(articles)


def is_lycoris_lora(lyco, models):
    """
        Compares a lycoris model to scanned loras to ensure that they're not the same file.
    """
    loras = None
    try:
        loras = models["lora"][lyco["hash"]]

    except (KeyError, ValueError):
        return False

    try:
        lyco_path = os.path.realpath(lyco["model_path"], strict=True)

        for lora in loras:
            lora_path = os.path.realpath(lora["model_path"], strict=True)
            if lyco_path == lora_path:
                return True

    except OSError:
        return False

    return False
