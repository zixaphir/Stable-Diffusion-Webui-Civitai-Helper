""" -*- coding: UTF-8 -*-
This extension can help you manage your models from civitai.
 It can download preview, add trigger words, open model page and use the prompt from preview image
repo: https://github.com/butaixianran/
"""

import os
import gradio as gr
import modules
from modules import scripts
from modules import shared
from modules import script_callbacks
from scripts.ch_lib import model
from scripts.ch_lib import js_action_civitai
from scripts.ch_lib import civitai
from scripts.ch_lib import util
from scripts import sections

# init
# root path
ROOT_PATH = os.getcwd()

# extension path
EXTENSION_PATH = scripts.basedir()

# default hidden values for civitai helper buttons
BUTTONS = {
    "replace_preview_button": False,
    "open_url_button": False,
    "add_trigger_words_button": False,
    "add_preview_prompt_button": False,
    "rename_model_button": False,
    "remove_model_button": False,
}

model.get_custom_model_folder()

def update_proxy():
    """ Set proxy, allow for changes at runtime """
    proxy = util.get_opts("ch_proxy")

    util.printD(f"Set Proxy: {proxy}")
    if proxy:
        util.PROXIES["http"] = proxy
        util.PROXIES["https"] = proxy
        return

    util.PROXIES["http"] = None
    util.PROXIES["https"] = None


def on_ui_tabs():
    # init
    # init_py_msg = {
    #     # relative extension path
    #     "EXTENSION_PATH": util.get_relative_path(EXTENSION_PATH, ROOT_PATH),
    # }
    # init_py_msg_str = json.dumps(init_py_msg)

    try:
        BUTTONS["add_trigger_words_button"] = util.newer_version(
            util.webui_version(), '1.5.0', allow_equal=True
        )
    except ValueError: # packaging.version.InvalidVersion
        BUTTONS["add_trigger_words_button"] = False

    # get prompt textarea
    # check modules/ui.py, search for txt2img_paste_fields
    # Negative prompt is the second element
    txt2img_prompt = modules.ui.txt2img_paste_fields[0][0]
    txt2img_neg_prompt = modules.ui.txt2img_paste_fields[1][0]
    img2img_prompt = modules.ui.img2img_paste_fields[0][0]
    img2img_neg_prompt = modules.ui.img2img_paste_fields[1][0]

    # Used by some elements to pass messages to python
    js_msg_txtbox = gr.Textbox(
        label="Request Msg From Js",
        visible=False,
        lines=1,
        value="",
        elem_id="ch_js_msg_txtbox"
    )

    # ====UI====
    with gr.Blocks(
        analytics_enabled=False
    ) as civitai_helper:
    # with gr.Blocks(css=".block.padded {padding: 10px !important}") as civitai_helper:

        # init
        with gr.Box(elem_classes="ch_box"):
            sections.scan_models_section()

        with gr.Box(elem_classes="ch_box"):
            sections.get_model_info_by_url_section()

        with gr.Box(elem_classes="ch_box"):
            gr.Markdown("### Download Model")
            with gr.Tab("Single"):
                sections.download_section()
            with gr.Tab("Batch Download"):
                sections.download_multiple_section()

        with gr.Box(elem_classes="ch_box"):
            sections.scan_for_duplicates_section()

        with gr.Box(elem_classes="ch_box"):
            sections.check_new_versions_section(js_msg_txtbox)

        # ====Footer====
        gr.HTML(f"<center>{util.SHORT_NAME} version: {util.VERSION}</center>")

        # ====hidden component for js, not in any tab====
        js_msg_txtbox.render()
        py_msg_txtbox = gr.Textbox(
            label="Response Msg From Python",
            visible=False,
            lines=1,
            value="",
            elem_id="ch_py_msg_txtbox"
        )

        js_open_url_btn = gr.Button(
            value="Open Model Url",
            visible=False,
            elem_id="ch_js_open_url_btn"
        )
        js_add_trigger_words_btn = gr.Button(
            value="Add Trigger Words",
            visible=False,
            elem_id="ch_js_add_trigger_words_btn"
        )
        js_use_preview_prompt_btn = gr.Button(
            value="Use Prompt from Preview Image",
            visible=False,
            elem_id="ch_js_use_preview_prompt_btn"
        )
        js_rename_card_btn = gr.Button(
            value="Rename Card",
            visible=False,
            elem_id="ch_js_rename_card_btn"
        )
        js_remove_card_btn = gr.Button(
            value="Remove Card",
            visible=False,
            elem_id="ch_js_remove_card_btn"
        )

        # ====events====
        # js action
        js_open_url_btn.click(
            js_action_civitai.open_model_url,
            inputs=[js_msg_txtbox],
            outputs=py_msg_txtbox
        )
        js_add_trigger_words_btn.click(
            js_action_civitai.add_trigger_words,
            inputs=[js_msg_txtbox],
            outputs=[
                txt2img_prompt, img2img_prompt
            ]
        )
        js_use_preview_prompt_btn.click(
            js_action_civitai.use_preview_image_prompt,
            inputs=[js_msg_txtbox],
            outputs=[
                txt2img_prompt, txt2img_neg_prompt,
                img2img_prompt, img2img_neg_prompt
            ]
        )
        js_rename_card_btn.click(
            js_action_civitai.rename_model_by_path,
            inputs=[js_msg_txtbox],
            outputs=py_msg_txtbox
        )
        js_remove_card_btn.click(
            js_action_civitai.remove_model_by_path,
            inputs=[js_msg_txtbox],
            outputs=py_msg_txtbox
        )

    # the third parameter is the element id on html, with a "tab_" as prefix
    return ((civitai_helper, "Civitai Helper", "civitai_helper"),)


def on_ui_settings():
    section = ('civitai_helper', "Civitai Helper")
    shared.opts.add_option(
        "ch_civiai_api_key",
        shared.OptionInfo(
            "",
            (
                "API key for authenticating with Civitai. "
                "This is required to download some models. "
                "See Wiki for more details."
            ),
            gr.Textbox,
            {"interactive": True, "max_lines": 1},
            section=section
        ).link(
            "Wiki",
            "https://github.com/zixaphir/Stable-Diffusion-Webui-Civitai-Helper/wiki/Civitai-API-Key"
        )
    )
    shared.opts.add_option(
        "ch_dl_lyco_to_lora",
        shared.OptionInfo(
            False,
            (
                "Save LyCORIS models to Lora directory. Do not use this if you are on "
                "older versions of webui or you use an extension that handles LyCORIS "
                "models."
            ),
            gr.Checkbox,
            {"interactive": True},
            section=section)
    )
    shared.opts.add_option(
        "ch_open_url_with_js",
        shared.OptionInfo(
            True,
            (
                "Open model Url on the user's client side, rather than server side. "
                "If you are running WebUI locally, disabling this may open URLs in your "
                "default internet browser if it is different than the one you are running "
                "WebUI in"
            ),
            gr.Checkbox,
            {"interactive": True},
            section=section
        )
    )
    shared.opts.add_option(
        "ch_hide_buttons",
        shared.OptionInfo(
           [x for x, y in BUTTONS.items() if y],
           "Hide checked Civitai Helper buttons on model cards",
           gr.CheckboxGroup,
           {"choices": list(BUTTONS)},
           section=section
        )
   )
    shared.opts.add_option(
        "ch_always_display",
        shared.OptionInfo(
            False,
            "Always Display Buttons on model cards",
            gr.Checkbox,
            {"interactive": True},
            section=section
        )
    )
    shared.opts.add_option(
        "ch_show_btn_on_thumb",
        shared.OptionInfo(
            True,
            "Show Button On Thumb Mode in SD webui versions before 1.5.0",
            gr.Checkbox,
            {"interactive": True},
            section=section
        )
    )
    shared.opts.add_option(
        "ch_max_size_preview",
        shared.OptionInfo(
            True,
            "Download Max Size Preview",
            gr.Checkbox,
            {"interactive": True},
            section=section
        )
    )
    shared.opts.add_option(
        "ch_nsfw_threshold",
        shared.OptionInfo(
            list(civitai.NSFW_LEVELS.keys())[0], # Block NSFW
            util.dedent(
                """
                Blocks images that are more NSFW than the chosen rating.
                "XXX" allows all NSFW images unless Civitai changes their
                rating system.
                """
            ).strip().replace("\n", " "),
            gr.Dropdown,
            {
                "choices": list(civitai.NSFW_LEVELS.keys()),
                "interactive": True
            },
            section=section
        )
    )
    shared.opts.add_option(
        "ch_dl_webui_metadata",
        shared.OptionInfo(
            True,
            "Also add data for WebUI metadata editor",
            gr.Checkbox,
            {"interactive": True},
            section=section)
    )
    shared.opts.add_option(
        "ch_proxy",
        shared.OptionInfo(
            "",
            "Proxy to use for fetching models and model data. Format:  http://127.0.0.1:port",
            gr.Textbox,
            {"interactive": True, "max_lines": 1},
            section=section)
    )
    shared.opts.onchange(
        "ch_proxy",
        update_proxy
    )


script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_ui_tabs(on_ui_tabs)
