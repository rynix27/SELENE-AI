"""
build_website.py
==================
Regenerates outputs/index.html from website_template.html + a fresh run of
the pipeline (via export_web_data.py). Run this any time data_simulator.py
or a scoring/planning module changes, so the website never drifts from the
pipeline's actual output.

The template references ../assets/styles.css and ../assets/app.js (relative
to outputs/), so keep the assets/ folder alongside outputs/ at the repo
root -- nothing needs to be copied, the relative paths already line up.

Usage:
    python3 build_website.py
"""

import os
from export_web_data import main as export_data

TEMPLATE_PATH = "website_template.html"
DATA_PATH = "outputs/website_data.json"
OUTPUT_PATH = "outputs/index.html"


def build():
    os.makedirs("outputs", exist_ok=True)
    export_data(out_path=DATA_PATH)

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()
    with open(DATA_PATH, encoding="utf-8") as f:
        data_json = f.read()

    final = template.replace("__SELENE_DATA_JSON__", data_json)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(final)

    print(f"Built {OUTPUT_PATH} ({os.path.getsize(OUTPUT_PATH)/1024:.1f} KB)")


if __name__ == "__main__":
    build()
