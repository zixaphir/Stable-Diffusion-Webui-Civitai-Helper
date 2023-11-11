""" -*- coding: UTF-8 -*-
Sections for civitai_helper tab.
"""

import gradio as gr
from scripts.ch_lib import model
from scripts.ch_lib import js_action_civitai
from scripts.ch_lib import model_action_civitai
from scripts.ch_lib import civitai
from scripts.ch_lib import duplicate_check
from scripts.ch_lib import util

model_types = list(model.folders.keys())

def scan_models_section():
    """ Scan Models Section """
    with gr.Row():
        gr.Markdown("### Scan Models for Civitai")
    with gr.Row():
        with gr.Column():
            scan_model_types_drop = gr.CheckboxGroup(
                choices=model_types,
                label="Model Types",
                value=model_types
            )
            nsfw_preview_scan_drop = gr.Dropdown(
                label="Block NSFW Level Above",
                choices=civitai.NSFW_LEVELS[1:],
                value=util.get_opts("ch_nsfw_preview_threshold"),
                elem_id="ch_nsfw_preview_scan_drop"
            )
    with gr.Row():
        with gr.Column():
            refetch_old_ckb = gr.Checkbox(
                label="Replace Old Metadata Formats*",
                value=False,
                elem_id="ch_refetch_old_ckb"
            )
            gr.HTML("""
                * [<a href=https://github.com/zixaphir/Stable-Diffusion-Webui-Civitai-Helper/wiki/Metadata-Format-Changes>wiki</a>] Do not use this option if you have made changes with the metadata editor without backing up your data!!<br><br>
                """)

        with gr.Column():
            scan_model_civitai_btn = gr.Button(
                value="Scan",
                variant="primary",
                elem_id="ch_scan_model_civitai_btn"
            )

            scan_civitai_info_image_meta_btn = gr.Button(
                value="Update image generation information (Experimental)",
                variant="primary",
                elem_id="ch_Scan_civitai_info_image_meta_btn"
            )

    with gr.Row():
        scan_model_log_md = gr.Markdown(
            value="Scanning takes time, just wait. Check console log for details",
            elem_id="ch_scan_model_log_md"
        )

    # ====events====
    scan_model_civitai_btn.click(
        model_action_civitai.scan_model,
        inputs=[
            scan_model_types_drop,
            nsfw_preview_scan_drop, refetch_old_ckb
        ],
        outputs=scan_model_log_md
    )

    scan_civitai_info_image_meta_btn.click(
        model.scan_civitai_info_image_meta,
        outputs=scan_model_log_md
    )

def get_model_info_by_url_section():
    """ Get Civitai Model Info by Model Page URL Section """

    def get_model_names_by_input(model_type, empty_info_only):
        names = civitai.get_model_names_by_input(model_type, empty_info_only)
        return model_name_drop.update(choices=names)

    no_info_model_names = civitai.get_model_names_by_input("ckp", False)

    with gr.Column():
        gr.Markdown("### Get Model Info from Civitai by URL")
        gr.Markdown("Use this when scanning can not find a local model on civitai")
        with gr.Row():
            with gr.Column(scale=2):
                model_type_drop = gr.Dropdown(
                    choices=model_types,
                    label="Model Type",
                    value="ckp",
                    multiselect=False,
                    elem_classes="ch_vpadding"
                )
            with gr.Column(scale=1):
                empty_info_only_ckb = gr.Checkbox(
                    label="Only Show Models have no Info",
                    value=False,
                    elem_id="ch_empty_info_only_ckb",
                    elem_classes="ch_vpadding"
                )
        with gr.Row():
            with gr.Column(scale=2):
                model_name_drop = gr.Dropdown(
                    choices=no_info_model_names,
                    label="Model",
                    value="",
                    multiselect=False
                )
            with gr.Column(scale=1):
                nsfw_preview_url_drop = gr.Dropdown(
                    label="Block NSFW Level Above",
                    choices=civitai.NSFW_LEVELS[1:],
                    value=util.get_opts("ch_nsfw_preview_threshold"),
                    elem_id="ch_nsfw_preview_url_drop"
                )
        with gr.Row():
            with gr.Column(scale=2, elem_classes="justify-bottom"):
                model_url_or_id_txtbox = gr.Textbox(
                    label="Civitai URL",
                    lines=1,
                    value=""
                )
            with gr.Column(scale=1, elem_classes="justify-bottom"):
                get_civitai_model_info_by_id_btn = gr.Button(
                    value="Get Model Info from Civitai",
                    variant="primary"
                )

    get_model_by_id_log_md = gr.Markdown("")

    # ====events====
    model_type_drop.change(
        get_model_names_by_input,
        inputs=[
            model_type_drop, empty_info_only_ckb
        ],
        outputs=model_name_drop
    )
    empty_info_only_ckb.change(
        get_model_names_by_input,
        inputs=[
            model_type_drop, empty_info_only_ckb
        ],
        outputs=model_name_drop
    )

    get_civitai_model_info_by_id_btn.click(
        model_action_civitai.get_model_info_by_input,
        inputs=[
            model_type_drop, model_name_drop,
            model_url_or_id_txtbox, nsfw_preview_url_drop
        ],
        outputs=get_model_by_id_log_md
    )

def download_section():
    """ Download Models Section """

    dl_state = gr.State({
        "model_info": {},
        "filenames": {
            # dl_version_str: filename,
        },
        "previews": {
            # dl_version_str: [{url: url, nsfw: nsfw}],
        }
    })

    def get_model_info_by_url(url, subfolder):
        data = model_action_civitai.get_model_info_by_url(url)

        if not data:
            return None

        dl_state = {
            "model_info": {},
            "filenames": {},
            "previews": {}
        }

        subfolders = data["subfolders"]
        version_strs = data["version_strs"]
        filenames = data["filenames"]

        if subfolder == "" or subfolder not in subfolders:
            subfolder = "/"

        dl_state["model_info"] = data["model_info"]
        dl_state["previews"] = data["previews"]

        for filename, version in zip(filenames, version_strs):
            dl_state["filenames"][version] = filename

        return [
            dl_state, data["model_name"], data["model_type"],
            dl_subfolder_drop.update(
                choices=subfolders,
                value=subfolder
            ),
            dl_version_drop.update(
                choices=version_strs,
                value=version_strs[0]
            )
        ]

    def filter_previews(previews, nsfw_preview_url_drop):
        images = []
        for preview in previews:
            nsfw = preview["nsfw"]
            if not civitai.should_skip(nsfw_preview_url_drop, nsfw):
                images.append(preview["url"])

        return images

    def update_dl_inputs(dl_version, state, nsfw_threshold, current_preview):
        filename = state["filenames"][dl_version]

        if not filename:
            filename = dl_filename_txtbox.value

        file_parts = filename.split(".")
        ext = file_parts.pop()
        base = ".".join(file_parts)

        previews = filter_previews(state["previews"][dl_version], nsfw_threshold)

        preview = None
        if len(previews) > 0:
            if current_preview in previews:
                preview = current_preview
            else:
                preview = previews[0]

        return [
            dl_filename_txtbox.update(
                value=base
            ),
            dl_extension_txtbox.update(
                value=ext
            ),
            dl_previews_drop.update(
                choices=previews,
                value=preview
            )
        ]

    def update_dl_preview(dl_previews_drop):
        return dl_preview_img.update(
            value=dl_previews_drop
        )

    with gr.Row():
        gr.Markdown("### Download Model")

    with gr.Row():
        with gr.Column(scale=2, elem_id="ch_dl_model_inputs"):
            with gr.Row():
                with gr.Column(scale=2, elem_classes="justify-bottom"):
                    dl_model_url_or_id_txtbox = gr.Textbox(
                        label="Civitai URL",
                        lines=1,
                        max_lines=1,
                        value="",
                        placeholder="Model URL or ID"
                    )
                with gr.Column(elem_classes="justify-bottom"):
                    dl_model_info_btn = gr.Button(
                        value="1. Get Model Info by Civitai Url",
                        variant="primary"
                    )

            gr.Markdown(value="2. Pick Subfolder and Model Version")
            with gr.Row():
                with gr.Column():
                    dl_model_name_txtbox = gr.Textbox(
                        label="Model Name",
                        interactive=False,
                        lines=1,
                        max_lines=1,
                        value=""
                    )
                    dl_subfolder_drop = gr.Dropdown(
                        choices=[],
                        label="Sub-folder",
                        value="",
                        interactive=True,
                        multiselect=False
                    )
                with gr.Column():
                    dl_model_type_txtbox = gr.Textbox(
                        label="Model Type",
                        interactive=False,
                        lines=1,
                        max_lines=1,
                        value=""
                    )
                    dl_duplicate_drop = gr.Dropdown(
                        choices=["Skip", "Overwrite", "Rename New"],
                        label="Duplicate File Behavior",
                        value="Skip",
                        interactive=True,
                        multiselect=False
                    )
                with gr.Column():
                    dl_version_drop = gr.Dropdown(
                        choices=[],
                        label="Model Version",
                        value="",
                        interactive=True,
                        multiselect=False
                    )
                    nsfw_preview_dl_drop = gr.Dropdown(
                        label="Block NSFW Level Above",
                        choices=civitai.NSFW_LEVELS[1:],
                        value=util.get_opts("ch_nsfw_preview_threshold"),
                        elem_id="ch_nsfw_preview_dl_drop"
                    )

            with gr.Row():
                dl_all_ckb = gr.Checkbox(
                    label="Download All files",
                    value=False,
                    elem_id="ch_dl_all_ckb",
                    elem_classes="ch_vpadding"
                )

            with gr.Row():
                with gr.Column(scale=2, elem_classes="justify-bottom"):
                    dl_filename_txtbox = gr.Textbox(
                        label="Model filename",
                        value="",
                        lines=1,
                        max_lines=1,
                        elem_id="ch_dl_filename_txtbox",
                        elem_classes="ch_vpadding"
                    )
                    dl_extension_txtbox = gr.Textbox(
                        label="Model extension",
                        value="",
                        elem_id="ch_dl_extension_txtbox",
                        visible=False
                    )

                with gr.Column(elem_classes="justify-bottom"):
                    dl_civitai_model_by_id_btn = gr.Button(
                        value="3. Download Model",
                        elem_classes="ch_vmargin",
                        variant="primary"
                    )
            with gr.Row():
                for filetype in ["Model", "Training Data", "Config", "VAE"]:
                    print(filetype)


        with gr.Column(scale=1, elem_id="ch_preview_img"):
            with gr.Row():
                dl_previews_drop = gr.Dropdown(
                    choices=[],
                    label="Preview Image Selection",
                    value="",
                    elem_id="ch_dl_previews_drop",
                )
            with gr.Row():
                dl_preview_img = gr.Image(
                    label="Preview Image",
                    value=None,
                    elem_id="ch_dl_preview_img",
                    width=256
                )
    with gr.Row():
        dl_log_md = gr.Markdown(
            value="Check Console log for Downloading Status"
        )

    # ====events====
    dl_model_info_btn.click(
        get_model_info_by_url,
        inputs=[
            dl_model_url_or_id_txtbox, dl_subfolder_drop
        ],
        outputs=[
            dl_state, dl_model_name_txtbox,
            dl_model_type_txtbox, dl_subfolder_drop,
            dl_version_drop
        ]
    )
    dl_civitai_model_by_id_btn.click(
        model_action_civitai.dl_model_by_input,
        inputs=[
            dl_state, dl_model_type_txtbox,
            dl_subfolder_drop, dl_version_drop,
            dl_filename_txtbox, dl_extension_txtbox,
            dl_all_ckb, nsfw_preview_dl_drop,
            dl_duplicate_drop, dl_previews_drop
        ],
        outputs=dl_log_md
    )
    dl_version_drop.change(
        update_dl_inputs,
        inputs=[dl_version_drop, dl_state, nsfw_preview_dl_drop, dl_previews_drop],
        outputs=[
            dl_filename_txtbox, dl_extension_txtbox,
            dl_previews_drop
        ]
    )
    nsfw_preview_dl_drop.change(
        update_dl_inputs,
        inputs=[dl_version_drop, dl_state, nsfw_preview_dl_drop, dl_previews_drop],
        outputs=[
            dl_filename_txtbox, dl_extension_txtbox,
            dl_previews_drop
        ]
    )
    dl_previews_drop.change(
        update_dl_preview,
        inputs=dl_previews_drop,
        outputs=dl_preview_img
    )

def scan_for_duplicates_section():
    """ Scan Duplicate Models Section """
    with gr.Column():
        gr.Markdown("### Scan for duplicate models")
        with gr.Row():
            with gr.Column():
                scan_dup_model_types_drop = gr.CheckboxGroup(
                    choices=model_types,
                    label="Model Types",
                    value=model_types
                )
        with gr.Row():
            with gr.Column(scale=2):
                cached_hash_ckb = gr.Checkbox(
                    label="Use Hash from Metadata (May have false-positives but can be useful if you've pruned models)",
                    value=False,
                    elem_id="ch_cached_hash_ckb"
                )
            with gr.Column():
                scan_dup_model_btn = gr.Button(
                    value="Scan",
                    variant="primary",
                    elem_id="ch_scan_dup_model_civitai_btn"
                )

        # with gr.Row():
        scan_dup_model_log_md = gr.HTML(
            value="Scanning takes time, just wait. Check console log for details",
            elem_id="ch_scan_dup_model_log_md"
        )

    # ====events====
    scan_dup_model_btn.click(
        duplicate_check.scan_for_dups,
        inputs=[
            scan_dup_model_types_drop,
            cached_hash_ckb
        ],
        outputs=scan_dup_model_log_md
    )

def check_new_versions_section(js_msg_txtbox):
    """ Check models' new version section """

    with gr.Column():
        gr.Markdown("### Check models' new version")
        with gr.Row():
            with gr.Column(scale=2):
                model_types_ckbg = gr.CheckboxGroup(
                    choices=model_types,
                    label="Model Types",
                    value=[
                        "ti", "hyper", "ckp", "lora", "lycoris"
                    ]
                )
                nsfw_preview_update_drop = gr.Dropdown(
                    label="Block NSFW Level Above",
                    choices=civitai.NSFW_LEVELS[1:],
                    value=util.get_opts("ch_nsfw_preview_threshold"),
                    elem_id="ch_nsfw_preview_dl_drop"
                )
        with gr.Row():
            with gr.Column(scale=2):
                check_models_new_version_btn = gr.Button(
                    value="Check New Version from Civitai",
                    variant="primary"
                )

        with gr.Row():
            with gr.Column():
                dl_new_version_log_md = gr.Markdown()
                check_models_new_version_log_md = gr.HTML(
                    "It takes time, just wait. Check console log for details"
                )

    # ====events====
    check_models_new_version_btn.click(
        model_action_civitai.check_models_new_version_to_md,
        inputs=model_types_ckbg,
        outputs=check_models_new_version_log_md
    )

    js_dl_model_new_version_btn = gr.Button(
        value="Download Model's new version",
        visible=False,
        elem_id="ch_js_dl_model_new_version_btn"
    )

    js_dl_model_new_version_btn.click(
        js_action_civitai.dl_model_new_version,
        inputs=[
            js_msg_txtbox,
            nsfw_preview_update_drop
        ],
        outputs=dl_new_version_log_md
    )
