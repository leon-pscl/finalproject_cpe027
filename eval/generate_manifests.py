r"""Generate dataset manifests for the DSP evaluation.

The script walks the external dataset root defined by the environment variable
`EVAL_DATA_ROOT` (default ``E:\Datasets``) and creates one JSON manifest per
required dataset under `eval/manifests/`.
"""

import json
import os
from pathlib import Path

# Constants for required datasets
DATASETS = {
    "acl6060": {
        "subpath": "(ACL6060)2023.iwslt-1.2.dataset",
        "required": True,
    },
    "demand_kitchen": {
        "subpath": os.path.join("DEMAND", "DKITCHEN_16k"),
        "required": True,
    },
    "loquacious_dev": {
        "subpath": os.path.join("loquacious", "dev"),
        "required": True,
    },
    "loquacious_test": {
        "subpath": os.path.join("loquacious", "test"),
        "required": True,
    },
    "m3av": {
        "subpath": "M3AV",
        "required": False,  # may be incomplete
    },
    "musan": {
        "subpath": os.path.join("MUSAN", "musan.tar.gz"),
        "required": False,
    },
}


def main() -> None:
    root = Path(os.getenv("EVAL_DATA_ROOT", r"E:\Datasets"))
    manifests_dir = Path("eval/manifests")
    manifests_dir.mkdir(parents=True, exist_ok=True)

    for name, info in DATASETS.items():
        path = root / info["subpath"]
        manifest = {
            "id": name,
            "path": str(path),
            "exists": path.exists(),
            "required": info["required"],
        }
        # Simple placeholder for checksum / licence – to be filled manually later
        manifest["checksum"] = None
        manifest["license"] = None
        manifest["reference_provenance"] = None
        out_file = manifests_dir / f"{name}.json"
        out_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Wrote manifest {out_file} (exists={path.exists()})")


if __name__ == "__main__":
    main()
