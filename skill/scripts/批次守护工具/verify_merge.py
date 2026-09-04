#!/usr/bin/env python3
"""
Batch Guard: verify merged draft contains all batch contents.

This is a content-presence check (substring) intended to catch accidental omissions.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def verify_merge(plan_path: Path, workdir: Path, merged_path: Path) -> Tuple[bool, List[str]]:
    if not merged_path.exists():
        return False, [f"Merged file not found: {merged_path}"]

    merged_content = merged_path.read_text(encoding="utf-8")
    indices = _batch_indices_from_plan(plan_path) or _batch_indices_from_files(workdir)
    if not indices:
        return False, ["No batches found to verify."]

    errors: List[str] = []
    for idx in indices:
        batch_file = workdir / f"正文_Batch{idx}.md"
        if not batch_file.exists():
            errors.append(f"Missing batch file: {batch_file}")
            continue
        batch_content = batch_file.read_text(encoding="utf-8").strip()
        if batch_content and batch_content not in merged_content:
            errors.append(f"Batch content not found in merged file: {batch_file}")

    return not errors, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Guard: verify merged draft includes all batches.")
    parser.add_argument("--plan", default="output/work/thesis_writing_plan.md", help="Path to thesis writing plan")
    parser.add_argument("--workdir", default="output/work", help="Directory containing 正文_Batch*.md")
    parser.add_argument("--merged", default="output/work/正文_合并_v1.md", help="Merged markdown path")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"❌ Plan file not found: {plan_path}")
        sys.exit(1)

    ok, errors = verify_merge(plan_path=plan_path, workdir=Path(args.workdir), merged_path=Path(args.merged))
    if ok:
        print("✅ Merge verification passed (all batch contents found).")
        sys.exit(0)

    print("❌ Merge verification failed:")
    for msg in errors:
        print(f"  - {msg}")
    sys.exit(1)


if __name__ == "__main__":
    main()
