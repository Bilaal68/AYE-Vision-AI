# -*- coding: utf-8 -*-
"""
Master compiler that stitches together all parts of TECHNICAL_DOCUMENTATION.md.
"""
import os
import sys

# Ensure local scripts dir is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from part_1_3 import CONTENT_1, CONTENT_2, CONTENT_3
from part_4_5 import CONTENT_4, CONTENT_5
from part_6_7 import CONTENT_6, CONTENT_7
from part_8_appendices import CONTENT_8, CONTENT_APP

def compile_all():
    target_path = "TECHNICAL_DOCUMENTATION.md"
    print(f"Compiling complete master documentation to {target_path}...")

    full_doc = "\n\n".join([
        CONTENT_1.strip(),
        CONTENT_2.strip(),
        CONTENT_3.strip(),
        CONTENT_4.strip(),
        CONTENT_5.strip(),
        CONTENT_6.strip(),
        CONTENT_7.strip(),
        CONTENT_8.strip(),
        CONTENT_APP.strip(),
        ""
    ])

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(full_doc)

    lines = len(full_doc.splitlines())
    bytes_count = len(full_doc.encode("utf-8"))
    print(f"Documentation generated successfully: {lines} lines, {bytes_count} bytes.")

if __name__ == "__main__":
    compile_all()
