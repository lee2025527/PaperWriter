#!/usr/bin/env python3
"""
Merge batches into a clean thesis draft.

Rules:
- Follow the order defined in output/work/thesis_writing_plan.md (Batch Manifest).
- Place Batch 7 (abstracts) at the very top:
  1) 中文摘要 + 中文关键词
  2) 英文摘要 + 英文关键词
- Insert a single "[TOC]" placeholder after abstracts.
- For every batch file, delete "## 批次承接摘要" (or "# 批次承接摘要") and everything after it.
  Also remove the immediately preceding '---' separator if it is directly adjacent.
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


def _extract_manifest(plan_content: str) -> Optional[Dict[str, Any]]:
    code_blocks = re.findall(
        r"```(?:yaml|yml)\s*\n(.*?)\n```",
        plan_content,
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


def _strip_transition_summary(md: str) -> str:
    """
    Remove "批次承接摘要" section and everything after it.
    Also remove an adjacent preceding '---' separator.
    """
    pattern = re.compile(r"(?m)^(#{1,2})\s*批次承接摘要\s*$")
    match = pattern.search(md)
    if not match:
        return md.rstrip() + "\n"

    cut = match.start()
    before = md[:cut].rstrip()

    # Remove trailing separator if it's the last block just before the transition heading
    before = re.sub(r"\n---\s*$", "", before, flags=re.MULTILINE).rstrip()
    return before.rstrip() + "\n"


def _split_abstracts(batch7_clean: str) -> Tuple[str, str]:
    """
    Split Batch 7 into Chinese and English blocks.
    Expect headings: '# 中文摘要' and '# Abstract' (case-insensitive).
    """
    normalized = batch7_clean.replace("\r\n", "\n")

    m = re.search(r"(?im)^\s*#\s*abstract\s*$", normalized)
    if not m:
        raise ValueError("Batch 7 does not contain '# Abstract' heading.")

    chinese_part = normalized[: m.start()].rstrip()
    english_part = normalized[m.start() :].rstrip()

    # Remove trailing/leading separators around the split to avoid duplicate rules
    chinese_part = re.sub(r"\n---\s*$", "", chinese_part, flags=re.MULTILINE).rstrip()
    english_part = re.sub(r"^\s*---\s*\n+", "", english_part).rstrip()

    return chinese_part + "\n", english_part + "\n"


def merge_clean(plan_path: Path, workdir: Path, output_path: Path) -> None:
    indices = _batch_indices_from_plan(plan_path) or _batch_indices_from_files(workdir)
    if not indices:
        raise ValueError("No batches found: missing Batch Manifest and no matching 正文_Batch*.md files.")

    if 7 not in indices:
        raise ValueError("Expected Batch 7 (abstracts) but it is not present in the plan/files.")

    def read_batch(idx: int) -> str:
        path = workdir / f"正文_Batch{idx}.md"
        if not path.exists():
            raise FileNotFoundError(f"Missing batch file: {path}")
        return path.read_text(encoding="utf-8")

    batch7_clean = _strip_transition_summary(read_batch(7))
    zh_abs, en_abs = _split_abstracts(batch7_clean)

    cleaned_body_parts: List[str] = []
    for idx in indices:
        if idx == 7:
            continue
        cleaned = _strip_transition_summary(read_batch(idx)).rstrip()
        if cleaned:
            cleaned_body_parts.append(cleaned)

    merged_parts: List[str] = [
        zh_abs.rstrip(),
        en_abs.rstrip(),
        "[TOC]",
        *cleaned_body_parts,
    ]

    merged = "\n\n".join(part for part in merged_parts if part.strip()).rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge batches into a clean thesis draft markdown file.")
    parser.add_argument("--plan", default="output/work/thesis_writing_plan.md", help="Path to thesis writing plan")
    parser.add_argument("--workdir", default="output/work", help="Directory containing 正文_Batch*.md")
    parser.add_argument("--output", default="output/work/正文_合并_v1.md", help="Output merged markdown path")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"❌ Plan file not found: {plan_path}")
        sys.exit(1)

    try:
        merge_clean(plan_path=plan_path, workdir=Path(args.workdir), output_path=Path(args.output))
    except Exception as e:
        print(f"❌ Merge failed: {e}")
        sys.exit(1)

    print(f"✅ Clean merged output saved: {args.output}")


if __name__ == "__main__":
    main()

