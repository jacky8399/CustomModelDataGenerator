import argparse
import json
import os
from zipfile import ZipFile
import yaml

MAX_MODEL_DATA = 1 << 24
SIZE = 32
SIGN = 1 << SIZE - 1
def str_hash(str : str) -> int:
    h = 0
    for c in str:
        h = (31 * h + (ord(c) & 0xFF))
        h = (h & SIGN - 1) - (h & SIGN) # Simulate Java integer overflow
    return h % MAX_MODEL_DATA

parser = argparse.ArgumentParser('Generate model overrides given a list of custom model data values')

parser.add_argument('-o', '--output', default='output',
                    help='Folder to output to')
parser.add_argument('jarfile', help='The Minecraft .jar file.')
parser.add_argument('descfile', help='The description file.')

args = parser.parse_args()

constants = {}

def str_to_model_data(str) -> int:
    try:
        return int(str)
    except ValueError:
        pass

    if str in constants:
        return str_to_model_data(constants[str])
    else:
        return str_hash(str)

def resloc_to_path(str : str, root : str = 'models') -> str:
    split = str.split(':', 2)
    if len(split) == 1:
        ns, key = "minecraft", split[0]
    else:
        ns, key = split
    
    return f"assets/{ns}/{root}/{key}"

vanilla_models: dict[str, list[dict]] = {}
new_models = set()

with open(args.descfile, 'r') as f:
    descfile: dict[str, dict] = yaml.safe_load(f)

    for resloc, inner in descfile.items():
        if resloc == "__": # Define constants
            for k, v in inner.items():
                print(f"Defining constant {k} = {v}")
                constants[k] = v
            continue
    
        print(f"Parsing {resloc}")
        overrides: list[dict] = []
        for k, v in inner.items():
            model_name = str(v).replace('$1', k)
            new_models.add(model_name)
            overrides.append({
                "predicate": {
                    "custom_model_data": str_to_model_data(k)
                },
                "model": model_name
            })

        # Sort by custom model data, because Minecraft applies them from small to large
        overrides.sort(key=lambda d: d['predicate']['custom_model_data'])
        vanilla_models[resloc] = overrides

print(f"Fetching {len(vanilla_models)} vanilla models from JAR...")

updated_vanilla_models = {}
with ZipFile(args.jarfile, 'r') as zip:
    for k, v in vanilla_models.items():
        path = resloc_to_path("item/" + k) + ".json"
        print(f"Reading {path}")
        with zip.open(path, 'r') as modelfile:
            vanilla_model: dict = json.load(modelfile)

        # Handle the case where some items already have overrides
        vanilla_model["overrides"] = [*vanilla_model.get("overrides", []), *v]

        updated_vanilla_models[path] = vanilla_model
        # print(json.dumps(vanilla_model))

print(f"Writing {len(updated_vanilla_models)} updated vanilla models to {args.output}")
for model_path, json_obj in updated_vanilla_models.items():
    print("Writing " + model_path)

    path = os.path.join(args.output, model_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(json_obj, f)

print(f"Generating {len(new_models)} associated model files")
for model_name in new_models:
    model_path = resloc_to_path(model_name) + ".json"
    print("Writing " + model_path)

    path = os.path.join(args.output, model_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write('{"parent":"item/generated","textures":{"layer0":"' + model_name + '"}}')