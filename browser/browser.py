""" -*- coding: UTF-8 -*-
browser.py - Civitai Browser for Civitai Helper
"""

import os
from string import Template
import gradio as gr
from ch_lib import util
from ch_lib import civitai

def civitai_search():
    """
        Gradio UI
    """

    with gr.Blocks(
        analytics_enabled=False
    ) as browser:

        make_ui()

    return browser


def make_ui():
    ch_search_state = gr.State({
        "current_page": 0,
        "pages": []
    })

    def perform_search(
        state,
        query,
        tag,
        age,
        sort,
        base_models,
        types,
        allow_nsfw,
        evt: gr.EventData
    ):

        search = {}

        target = evt.target

        url = ""

        if target in [ch_prev_btn, ch_next_btn]:
            if target == ch_prev_btn:
                state["current_page"] = state["current_page"] - 1

            if target == ch_next_btn:
                state["current_page"] = state["current_page"] + 1

            url = state["pages"][state["current_page"]]

        if not url:
            search["query"] = query
            search["tag"] = tag
            search["period"] = age
            search["sort"] = sort
            search["baseModels"] = base_models
            search["types"] = types
            search["nsfw"] = "true" if allow_nsfw else "false"

            params = make_params(search)

            url = f"{civitai.URLS['query']}{params}"

        if len(state["pages"]) == 0:
            state["pages"].append(url)

        util.printD(f"Loading data from API request: {url}")

        json = civitai.civitai_get(url)

        if not json:
            return [
                {},
                "Civitai did not provide a useable response."
            ]

        content = parse_civitai_response(json)

        meta = content.get("meta", {})
        next_page = meta.get("next_page", None)

        if not next_page in state:
            state["pages"].append(next_page)

        cards = make_cards(content["models"])

        container = quick_template_from_file("container.html")

        return [
            state,
            container.safe_substitute({"cards": "".join(cards)}),
            ch_prev_btn.update(interactive=state["current_page"] > 0),
            ch_next_btn.update(interactive=next_page is not None)
        ]

    with gr.Row():
        gr.Markdown("# Browse and Search Civitai")

    with gr.Row(equal_height=True):
        ch_query_txt = gr.Textbox(
            label="Query",
            lines=1,
            value=""
        )
        ch_tag_txt = gr.Textbox(
            label="Tag",
            lines=1,
            value=""
        )
        #ch_nsfw_drop = gr.Dropdown(
        #    label="Allow NSFW",
        #    lines=1,
        #    value="false",
        #    choices=[
        #        "true",
        #        "false"
        #    ]
        #)
        ch_age_drop = gr.Dropdown(
            label="Model Age",
            lines=1,
            value="AllTime",
            choices=[
                "AllTime",
                "Year",
                "Month",
                "Week",
                "Day"
            ]
        )
        ch_sort_drop = gr.Dropdown(
            label="Model Age",
            lines=1,
            value="Newest",
            choices=[
                "Highest Rated",
                "Most Downloaded",
                "Newest"
            ]
        )

    with gr.Row(equal_height=True):
        ch_base_model_drop = gr.Dropdown(
            label="Base Model",
            lines=1,
            value=None,
            multiselect=True,
            choices=[
                # TODO: Perhaps make this list external so it can be updated independent of CH version.
                "Other",
                "Pix Art a",
                "Playground v2",
                "Pony",
                "SD 1.4",
                "SD 1.5",
                "SD 1.5 LCM",
                "SD 2.0",
                "SD 2.0 768",
                "SD 2.1",
                "SD 2.1 768",
                "SD 2.1 Unclip",
                "SDXL 0.9",
                "SDXL 1.0",
                "SDXL 1.0 LCM",
                "SDXL Distilled",
                "SDXL Lightning",
                "SDXL Turbo",
                "SVD",
                "SVD XT"
            ]
        )
        ch_type_drop = gr.Dropdown(
            label="Model Type",
            lines=1,
            value=None,
            multiselect=True,
            choices=[
                # TODO: Perhaps make this list external so it can be updated independent of CH version.
                "Checkpoint",
                "TextualInversion",
                "Hypernetwork",
                "AestheticGradient",
                "LORA",
                "LoCon",
                "Controlnet",
                "Poses",
                "Workflows",
                "MotionModule",
                "Upscaler",
                "Wildcards",
                "VAE"
            ]
        )

        ch_nsfw_ckb = gr.Checkbox(
            label="Allow NSFW",
            value=util.get_opts("ch_nsfw_threshold") != "PG",
            lines=1
        )

        ch_search_btn = gr.Button(
            variant="primary",
            value="Search",
            lines=1
        )

    with gr.Row(equal_height=True):
        ch_prev_btn = gr.Button(
            value="Previous Page",
            lines=1,
            interactive=False
        )
        ch_next_btn = gr.Button(
            value="Next Page",
            lines=1,
            interactive=False
        )

    with gr.Box():
        ch_search_results_html = gr.HTML(
            value="",
            label="Search Results",
            elem_id="ch_model_search_results"
        )

    inputs = [
        ch_search_state,
        ch_query_txt,
        ch_tag_txt,
        ch_age_drop,
        ch_sort_drop,
        ch_base_model_drop,
        ch_type_drop,
        ch_nsfw_ckb
    ]

    outputs = [
        ch_search_state,
        ch_search_results_html,
        ch_prev_btn,
        ch_next_btn
    ]

    ch_search_btn.click(
        perform_search,
        inputs=inputs,
        outputs=outputs
    )

    ch_prev_btn.click(
        perform_search,
        inputs=inputs,
        outputs=outputs
    )
    ch_next_btn.click(
        perform_search,
        inputs=inputs,
        outputs=outputs
    )

def array_frags(name, vals, frags):
    if len(vals) == 0:
        return frags

    for val in vals:
        frags.append(f"{name}={val}")

    return frags


def make_params(params):
    frags = []
    for key, val in params.items():
        if val == "":
            continue

        if key in ["types", "baseModels"]:
            frags = array_frags(key, val, frags)
            continue

        frags.append(f"{key}={val}")

    return '&'.join(frags)


def parse_model(model):
    name = model["name"]
    description = model["description"]
    url = f"{civitai.URLS['modelPage']}{model['id']}"
    model_type = model["type"]
    base_models = []
    preview = {
        type: None,
        url: None
    }
    versions = {
        # ID: base_model,
    }

    download = ""

    files = None
    model_versions = model["modelVersions"]

    if len(model_versions) > 0:
        files = model_versions[0].get("files", [])

    previews = []

    for version in model_versions:
        images = version.get("images", [])
        if len(images) > 0:
            previews = previews + images
        base_model = version.get("baseModel", None)
        if base_model and (base_model not in base_models):
            base_models.append(base_model)

        versions[version["id"]] = base_model

    for file in previews:
        # if not nsfw and (file.nsfwLevel > 2:
        #    continue
        if file["type"] != "image":
            continue

        preview["url"] = file["url"]
        preview["type"] = file["type"]
        break

    if files:
        for file in files:
            if file["type"] != "Model":
                continue
            download = file.get("downloadUrl", None)
            break

    return {
        "id": model["id"],
        "name": name,
        "preview": {
            "url": preview["url"],
            "type": preview["type"]
        },
        "url": url,
        "versions": versions,
        "description": description,
        "type": model_type,
        "download": download,
        "base_models": base_models,
    }

def parse_civitai_response(content):
    results = {
        "models": [],
        "meta": {
            "next_page": None
        }
    }

    if content.get("metadata", False):
        results["meta"]["next_page"] = content["metadata"].get("nextPage", None)

    for model in content["items"]:
        try:
            results["models"].append(parse_model(model))

        except Exception as e:
            # TODO: better error handling
            util.printD(e)
            util.printD(model)

    return results


def quick_template_from_file(filename):
    file = os.path.join(util.script_dir, "browser/templates", filename)
    with open(file, "r", encoding="utf-8") as text:
        template = Template(text.read())
    return template


def make_cards(models):
    card_template = quick_template_from_file("model_card.html")
    preview_template = quick_template_from_file("image_preview.html")
    # video_preview_template = quick_template_from_file("video_preview.html")

    cards = []
    for model in models:
        preview = ""
        if model["preview"]["url"]:
            preview = preview_template.safe_substitute({"preview_url": model["preview"]["url"]})

        card = card_template.safe_substitute({
            "name": model["name"],
            "preview": preview,
            "url": model["url"],
            "base_models": " / ".join(model["base_models"]),
            #"versions": model["versions"],
            "description": model["description"],
            "type": model["type"],
            "model_id": model["id"],
        })

        cards.append(card)

    return cards
