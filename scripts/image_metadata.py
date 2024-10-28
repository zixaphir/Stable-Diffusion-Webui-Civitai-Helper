import json
import re
import os
from pathlib import Path
from functools import reduce

from ch_lib import util
from modules import script_callbacks, extra_networks, prompt_parser, processing, sd_models
import networks
from backend.args import dynamic_args
import modules.processing_scripts.comments as comments

def add_resource_metadata(params):
    if not util.get_opts("ch_image_metadata") or 'parameters' not in params.pnginfo:
        return

    # StableDiffusionProcessing
    sd_processing = params.p
    # CheckpointInfo
    sd_checkpoint_info = sd_models.get_closet_checkpoint_match(sd_processing.sd_model_name)

    civitai_resource_list = []

    def add_civitai_resource(base_file_path, weight=None, type_name=None):
        try:
            # Read civitai metadata from previously generated info file
            file_path = Path(base_file_path).with_suffix(".civitai.info")
            with open(file_path, 'r') as file:
                civitai_info = json.load(file)
                resource_data = {}
                resource_data["type"] = type_name if type_name is not None else civitai_info["model"]["type"].lower()
                if resource_data["type"] in ["locon", "loha"]:
                    resource_data["type"] = "lycoris"
                if weight is not None:
                    resource_data["weight"] = weight
                resource_data["modelVersionId"] = civitai_info["id"]
                resource_data["modelName"] = civitai_info["model"]["name"]
                resource_data["modelVersionName"] = civitai_info["name"]
                civitai_resource_list.append(resource_data)
        except FileNotFoundError:
            util.printD(f"Warning: '{file_path}' not found. Did you forget to scan?")
        except Exception as e:
            util.printD(f"Civitai info error: {e}")

    # Add checkpoint metadata
    add_civitai_resource(Path(sd_checkpoint_info.filename).absolute())

    prompt_list = [[sd_processing.prompt, sd_processing.steps, True], [sd_processing.negative_prompt, sd_processing.steps, False]]
    extra_network_data = sd_processing.extra_network_data.values()

    # Add hires. fix data
    if isinstance(sd_processing, processing.StableDiffusionProcessingTxt2Img) and sd_processing.enable_hr:
        if sd_processing.hr_checkpoint_name is not None and sd_processing.hr_checkpoint_info.name_for_extra != sd_processing.sd_model_name:
            add_civitai_resource(Path(sd_processing.hr_checkpoint_info.filename).absolute())
        prompt_list += [[sd_processing.hr_prompt, sd_processing.hr_second_pass_steps, True], [sd_processing.hr_negative_prompt, sd_processing.hr_second_pass_steps, False]]
        extra_network_data = list(extra_network_data) + list(sd_processing.hr_extra_network_data.values())

    # Collect lora weights, skip duplicates
    extra_network_weights = {}
    if isinstance(extra_network_data, list) and len(extra_network_data) > 0 or not isinstance(extra_network_data, list) and any(extra_network_data):
        for extra_network_params in reduce(lambda list1, list2: list1 + list2, extra_network_data):
            extra_network_name = extra_network_params.positional[0]
            te_multiplier = float(extra_network_params.positional[1]) if len(extra_network_params.positional) > 1 else 1.0
            if extra_network_name not in extra_network_weights:
                extra_network_weights[extra_network_name] = te_multiplier

    # Add lora metadata
    for extra_network_name, te_multiplier in extra_network_weights.items():
        network_on_disk = networks.available_network_aliases.get(extra_network_name, None)
        add_civitai_resource(Path(network_on_disk.filename).absolute(), te_multiplier)

    # Get embedding file paths
    embed_filepaths = {}
    try:
        for dirpath, dirnames, filenames in os.walk(dynamic_args['embedding_dir'], followlinks=True):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if filepath.stat().st_size != 0 and filepath.suffix.upper() in ['.BIN', '.PT', '.SAFETENSORS']:
                    embed_filepaths[filepath.stem.strip().lower()] = filepath.absolute()
    except Exception as e:
        util.printD(f"Embedding directory error: {e}")

    # Add textual inversion embed metadata
    if len(embed_filepaths) > 0:
        embed_weights = {}
        try:
            embed_regex = re.compile(r"(?:^|[\s,])(" + '|'.join(re.escape(embed_name) for embed_name in embed_filepaths.keys()) + r")(?:$|[\s,])", re.IGNORECASE | re.MULTILINE)
            
            for prompt, steps, is_positive in prompt_list:
                # parse all special prompt rules
                comments_stripped = comments.strip_comments(prompt).strip()
                extra_networks_stripped, _ = extra_networks.parse_prompt(comments_stripped)
                if is_positive:
                    _, prompt_flat_list, _ = prompt_parser.get_multicond_prompt_list([extra_networks_stripped])
                else:
                    prompt_flat_list = [extra_networks_stripped]
                prompt_edit_schedule = prompt_parser.get_learned_conditioning_prompt_schedules(prompt_flat_list, steps)
                prompts = [text for step, text in reduce(lambda list1, list2: list1 + list2, prompt_edit_schedule)]
                for scheduled_prompt in prompts:
                    # calculate attention weights
                    for text, weight in prompt_parser.parse_prompt_attention(scheduled_prompt):
                        for match in embed_regex.findall(text):
                            # store final weight of embedding in dictionary
                            embed_weights[match.lower()] = weight
        except Exception as e:
            util.printD(f"Error parsing prompt for embeddings: {e}")

        # add final weights for embeddings
        for embed_name, weight in embed_weights.items():
            add_civitai_resource(embed_filepaths[embed_name], weight, "embed")

    if len(civitai_resource_list) > 0:
        params.pnginfo['parameters'] += f", Civitai resources: {json.dumps(civitai_resource_list, separators=(',', ':'))}"

script_callbacks.on_before_image_saved(add_resource_metadata)
