import json
import re
import os
from pathlib import Path

from ch_lib import util
from modules import script_callbacks, extra_networks, prompt_parser
import networks
from backend.args import dynamic_args

def add_resource_metadata(params):
    if 'parameters' not in params.pnginfo: return

    # StableDiffusionProcessing
    sd_processing = params.p

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
    add_civitai_resource(Path(sd_processing.sd_model.sd_checkpoint_info.filename).absolute())

    # Add extra network metadata (lora/lycoris/locon/etc.)
    for item in networks.loaded_networks:
        extra_network_params = next(x.positional for value in sd_processing.extra_network_data.values() for x in value if x.positional[0] == item.name)
        te_multiplier = float(extra_network_params[1]) if len(extra_network_params) > 1 else 1.0
        add_civitai_resource(Path(item.network_on_disk.filename).absolute(), te_multiplier)

    # Add textual inversion embed metadata
    if len(embed_filepaths) > 0:
        embed_regex = re.compile(r"(?:^|[\s,])(" + '|'.join(re.escape(embed_name) for embed_name in embed_filepaths.keys()) + r")(?:$|[\s,])", re.IGNORECASE | re.MULTILINE)
        for prompt in [sd_processing.prompt, sd_processing.negative_prompt]:
            # strip lora definitions, calculate attention weights
            for text, weight in prompt_parser.parse_prompt_attention(extra_networks.parse_prompt(prompt)[0]):
                for match in embed_regex.findall(text):
                    add_civitai_resource(embed_filepaths[match.lower()], weight, "embed")

    if len(civitai_resource_list) > 0:
        params.pnginfo['parameters'] += f", Civitai resources: {json.dumps(civitai_resource_list, separators=(',', ':'))}"

script_callbacks.on_before_image_saved(add_resource_metadata)
