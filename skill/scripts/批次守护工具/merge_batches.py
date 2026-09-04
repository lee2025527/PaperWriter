#!/usr/bin/env python3
"""
Batch Guard: deterministically merge batch markdown files into a single draft.

The merge operation is intentionally simple (concatenation in batch order) to avoid
dropping content.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


MANIFEST_VERSION = 1
MANIFEST_KEY = "batch_manifest_version"
MANIFEST_KEY_LEGACY = "auto_writer_batch_manifest_version"


def _extract_manifest(content: str) -> Optional[Dict[str, Any]]:
    code_blocks = re.findall(
        r"```(?:yaml|yml)\s*\n(.*?)\n```",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in code_blocks:
        if MANIFEST_KEY not in block and MANIFEST_KEY_LEGACY not in block:
            continue
        try:
            manifest = yaml.safe_load(block)
        except Exception:
            continue
        if not isinstance(manifest, dict):
            continue
        manifest_version = manifest.get(MANIFEST_KEY, manifest.get(MANIFEST_KEY_LEGACY))
        if manifest_version != MANIFEST_VERSION:
            continue
        if isinstance(manifest.get("batches"), list) and manifest["batches"]:
            return manifest
    return None


def _batch_indices_from_plan(plan_path: Path) -> List[int]:
    content = plan_path.read_text(encoding="utf-8")
    manifest = _extract_manifest(content)
    if not manifest:
        return []

    indices: List[int] = []
    for item in manifest["batches"]:
        if isinstance(item, dict) and isinstance(item.get("index"), int):
            indices.append(item["index"])
    return sorted(set(indices))


def _batch_indices_from_files(workdir: Path) -> List[int]:
    indices: List[int] = []
    for path in workdir.glob("正文_Batch*.md"):
        m = re.search(r"正文_Batch(\d+)\.md$", path.name)
        if m:
            indices.append(int(m.group(1)))
    return sorted(indices)


def merge_batches(plan_path: Path, workdir: Path, output_path: Path) -> None:
    indices = _batch_indices_from_plan(plan_path) or _batch_indices_from_files(workdir)
    if not indices:
        raise ValueError("No batches found: missing Batch Manifest and no matching 正文_Batch*.md files.")

    parts: List[str] = []
    for idx in indices:
        batch_file = workdir / f"正文_Batch{idx}.md"
        if not batch_file.exists():
            raise FileNotFoundError(f"Missing batch file: {batch_file}")
        parts.append(batch_file.read_text(encoding="utf-8").rstrip())

    merged = "\n\n---\n\n".join(parts).rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Guard: merge batch markdown files.")
    parser.add_argument("--plan", default="output/work/thesis_writing_plan.md", help="Path to thesis writing plan")
    parser.add_argument("--workdir", default="output/work", help="Directory containing 正文_Batch*.md")
    parser.add_argument("--output", default="output/work/正文_合并_v1.md", help="Output merged markdown path")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"❌ Plan file not found: {plan_path}")
        sys.exit(1)

    try:
        merge_batches(plan_path=plan_path, workdir=Path(args.workdir), output_path=Path(args.output))
    except Exception as e:
        print(f"❌ Merge failed: {e}")
        sys.exit(1)

    print(f"✅ Merged output saved: {args.output}")


if __name__ == "__main__":
    main()
