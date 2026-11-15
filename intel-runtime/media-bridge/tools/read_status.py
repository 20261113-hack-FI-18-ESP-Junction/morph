#!/usr/bin/env python3
"""Read configured loopback producer status without printing its private bearer."""
import argparse
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from morph_media_bridge.config import Config, private_token

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--config", type=Path, required=True)
args = parser.parse_args()
config = Config.load(args.config)
host = f"[{config.status_host}]" if ":" in config.status_host else config.status_host
request = Request(f"http://{host}:{config.status_port}/api/media/v1/status",
                  headers={"Authorization": "Bearer " + private_token(config.status_token_file)})
with urlopen(request, timeout=2) as response:
    print(json.dumps(json.load(response), indent=2))
