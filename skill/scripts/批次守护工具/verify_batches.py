#!/usr/bin/env python3
"""
Batch Guard: verify batch outputs exist and meet minimum completeness rules.

Designed to prevent "reported done but actually missing batches/content".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


MANIFEST_VERSION = 1
MANIFEST_KEY = "batch_manifest_version"
MANIFEST_KEY_LEGACY = "auto_writer_batch_manifest_version"


@dataclass(frozen=True)
class BatchSpec:
    index: int
    name: str
    target_word_count: int
    min_word_count: int
    require_transition_summary: bool
    cover_chapters: List[str]
    require_headings: List[str]


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


def _parse_batch_specs(plan_path: Path, require_manifest: bool) -> List[BatchSpec]:
    content = plan_path.read_text(encoding="utf-8")
    manifest = _extract_manifest(content)

    if manifest is None:
        if require_manifest:
            raise ValueError(
                "Missing Batch Manifest: plan does not contain a YAML block with "
                "`batch_manifest_version: 1` (or legacy "
                "`auto_writer_batch_manifest_version: 1`) and `batches:`."
            )
        return []

    specs: List[BatchSpec] = []
    for item in manifest["batches"]:
        if not isinstance(item, dict):
            continue

        index = item.get("index")
        name = item.get("name")
        target_word_count = item.get("target_word_count")
        min_word_count = item.get("min_word_count")

        if not isinstance(index, int):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(target_word_count, int) or target_word_count <= 0:
            continue

        if not isinstance(min_word_count, int) or min_word_count <= 0:
            min_word_count = int(target_word_count * 0.8)

        require_transition_summary = item.get("require_transition_summary", True)
        if not isinstance(require_transition_summary, bool):
            require_transition_summary = True

        cover_chapters = item.get("cover_chapters", [])
        if not isinstance(cover_chapters, list):
            cover_chapters = []

        require_headings = item.get("require_headings", [])
        if not isinstance(require_headings, list):
            require_headings = []

        specs.append(
            BatchSpec(
                index=index,
                name=name.strip(),
                target_word_count=target_word_count,
                min_word_count=min_word_count,
                require_transition_summary=require_transition_summary,
                cover_chapters=[str(x).strip() for x in cover_chapters if str(x).strip()],
                require_headings=[str(x).strip() for x in require_headings if str(x).strip()],
            )
        )

    specs.sort(key=lambda s: s.index)
    return specs


def _count_words(content: str) -> int:
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
    english_words = len(re.findall(r"\b[a-zA-Z]+\b", content))
    return chinese_chars + english_words


def _has_transition_summary(content: str) -> bool:
    markers = [
        "批次承接摘要",
        "承接摘要",
        "衔接摘要",
        "过渡摘要",
        "Batch Transition Summary",
    ]
    return any(m in content for m in markers)


def _missing_headings(content: str, required_headings: List[str]) -> List[str]:
    missing: List[str] = []
    for heading in required_headings:
        if heading and heading not in content:
            missing.append(heading)
    return missing


def verify_batches(
    plan_path: Path,
    workdir: Path,
    strict: bool,
    require_manifest: bool,
) -> Tuple[bool, Dict[str, Any]]:
    specs = _parse_batch_specs(plan_path, require_manifest=require_manifest)

    if not specs:
        return False, {
            "ok": False,
            "error": "No batch specs found. Add Batch Manifest to the plan or run with --require-manifest.",
        }

    results: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []

    for spec in specs:
        batch_file = workdir / f"正文_Batch{spec.index}.md"
        item: Dict[str, Any] = {
            "index": spec.index,
            "name": spec.name,
            "file": str(batch_file),
            "exists": batch_file.exists(),
            "non_empty": False,
            "word_count": 0,
            "min_word_count": spec.min_word_count,
            "transition_summary": False,
            "missing_headings": [],
        }

        if not batch_file.exists():
            errors.append(f"Missing batch file: {batch_file}")
            results.append(item)
            continue

        content = batch_file.read_text(encoding="utf-8").strip()
        if not content:
            errors.append(f"Empty batch file: {batch_file}")
            results.append(item)
            continue

        item["non_empty"] = True
        wc = _count_words(content)
        item["word_count"] = wc

        if wc < spec.min_word_count:
            errors.append(
                f"Batch {spec.index} too short: {wc} < min_word_count {spec.min_word_count} ({batch_file})"
            )

        if spec.require_transition_summary:
            item["transition_summary"] = _has_transition_summary(content)
            if not item["transition_summary"]:
                msg = f"Batch {spec.index} missing transition summary marker (expected '批次承接摘要' etc.)"
                if strict:
                    errors.append(msg)
                else:
                    warnings.append(msg)

        missing = _missing_headings(content, spec.require_headings)
        item["missing_headings"] = missing
        if missing:
            msg = f"Batch {spec.index} missing required headings: {missing}"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        if spec.cover_chapters:
            if not any(ch in content for ch in spec.cover_chapters):
                warnings.append(
                    f"Batch {spec.index} does not mention any cover_chapters {spec.cover_chapters} "
                    f"(may be OK if headings differ)"
                )

        results.append(item)

    ok = not errors
    report = {
        "ok": ok,
        "plan": str(plan_path),
        "workdir": str(workdir),
        "strict": strict,
        "require_manifest": require_manifest,
        "total_batches": len(specs),
        "errors": errors,
        "warnings": warnings,
        "batches": results,
    }
    return ok, report


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Guard: verify batch outputs.")
    parser.add_argument("--plan", default="output/work/thesis_writing_plan.md", help="Path to thesis writing plan")
    parser.add_argument("--workdir", default="output/work", help="Work directory containing batch files")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing transition summary / missing required headings as errors",
    )
    parser.add_argument(
        "--require-manifest",
        action="store_true",
        help="Fail if Batch Manifest is missing instead of attempting fallback",
    )
    parser.add_argument("--report", default=None, help="Optional path to save JSON report")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"❌ Plan file not found: {plan_path}")
        sys.exit(1)

    ok, report = verify_batches(
        plan_path=plan_path,
        workdir=Path(args.workdir),
        strict=args.strict,
        require_manifest=args.require_manifest,
    )

    if report.get("errors"):
        print("\n❌ Batch verification failed:")
        for msg in report["errors"]:
            print(f"  - {msg}")

    if report.get("warnings"):
        print("\n⚠️  Warnings:")
        for msg in report["warnings"]:
            print(f"  - {msg}")

    print(
        f"\nSummary: {report['total_batches']} batches checked, "
        f"ok={report['ok']} (strict={report['strict']})"
    )

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Report saved: {args.report}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
