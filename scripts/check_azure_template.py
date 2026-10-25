"""Check compiled startup files, catching literals that compile but fail in cloud-init."""
import argparse
import base64
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"/opt/image-pipeline/bootstrap.sh": "infra/azure/bootstrap.sh",
            "/opt/image-pipeline/bootstrap.yaml": "k8s/bootstrap.yaml"}


def check(template):
    variables = template["variables"]
    init = variables["init"]
    if not isinstance(init, dict):
        raise ValueError("Cloud-init must be a structured object, not an unevaluated template string")
    files = {item["path"]: item for item in init["write_files"]}
    if set(files) != set(EXPECTED):
        raise ValueError("Unexpected startup files")
    for path, source in EXPECTED.items():
        item = files[path]
        value = item["content"]
        if value.startswith("["):
            match = re.fullmatch(r"\[base64\(variables\('([^']+)'\)\)\]", value)
            if not match:
                raise ValueError("Unsupported startup content expression")
            content = variables[match[1]].encode()
        else:
            content = base64.b64decode(value, validate=True)
        if item["encoding"] != "b64" or content != (ROOT / source).read_bytes():
            raise ValueError("Startup file content differs from the source: " + path)
    if init["runcmd"] != [["bash", "/opt/image-pipeline/bootstrap.sh"]]:
        raise ValueError("Missing bootstrap command")
    vm = next(item for item in template["resources"] if item["type"] == "Microsoft.Compute/virtualMachines")
    custom = vm["properties"]["osProfile"]["customData"]
    if custom != "[base64(format('#cloud-config\n{0}', string(variables('init'))))]":
        raise ValueError("Unexpected cloud-config serialization")
    return {"status": "verified", "startup_files": list(files)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True)
    args = parser.parse_args()
    print(json.dumps(check(json.loads(Path(args.template).read_text()))))
