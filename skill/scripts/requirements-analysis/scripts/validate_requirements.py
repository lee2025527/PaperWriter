#!/usr/bin/env python3
"""Validate and patch 客户诉求.md to ensure required structure and fields exist."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


REQUIRED_SECTION_ORDER = [
    "## 客户基本信息",
    "## 明确要求清单",
    "## 研究范围与边界",
    "## 关键词",
]

DEFAULT_SECTION_LINES: Dict[str, List[str]] = {
    "## 客户基本信息": [
        "- 论文题目：",
        "- 专业/方向：",
        "- 任务类型：",
        "- 字数：",
        "- 查重/重复率要求：",
        "- AIGC/AI 检测要求：",
        "- 交稿时间：",
        "- 交付物格式：",
        "- 格式/引用规范：",
        "- 现有材料（路径）：",
    ],
    "## 明确要求清单": [
        "**必须做**",
        "- ",
        "",
        "**禁止做**",
        "- ",
        "",
        "**可选加分项**",
        "- ",
    ],
    "## 研究范围与边界": [
        "- 研究对象：",
        "- 场景/背景：",
        "- 研究范围：",
        "- 时间/地域范围：",
        "- 数据来源与限制：",
    ],
    "## 关键词": [
        "- 中文关键词：",
        "- 英文关键词：",
    ],
}

REQUIRED_FIELDS = {
    "## 客户基本信息": [
        "论文题目",
        "专业/方向",
        "任务类型",
        "字数",
        "查重/重复率要求",
        "AIGC/AI 检测要求",
        "交稿时间",
        "交付物格式",
        "格式/引用规范",
        "现有材料（路径）",
    ],
    "## 研究范围与边界": [
        "研究对象",
        "场景/背景",
        "研究范围",
        "时间/地域范围",
        "数据来源与限制",
    ],
    "## 关键词": [
        "中文关键词",
        "英文关键词",
    ],
}

PLACEHOLDER_VALUES = {"", "待确认", "待补充", "未提供", "n/a", "N/A"}
CRITICAL_FIELDS = {"论文题目", "中文关键词", "英文关键词"}
CONTRACT_REQUIRED_JSON_PATHS = [
    ("status", "status"),
    ("project_intent.title", "project_intent.title"),
    ("project_intent.task_type", "project_intent.task_type"),
    ("hard_constraints.word_count", "hard_constraints.word_count"),
    ("hard_constraints.deliverable_format", "hard_constraints.deliverable_format"),
    ("keywords.zh", "keywords.zh"),
    ("keywords.en", "keywords.en"),
    ("materials", "materials"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and patch output/work/客户诉求.md structure.",
    )
    parser.add_argument(
        "--requirements",
        default="output/work/客户诉求.md",
        help="客户诉求.md 路径",
    )
    parser.add_argument(
        "--input-dir",
        default="input",
        help="输入资料目录，用于自动填充现有材料路径与关键词",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="允许关键字段缺失时仍返回 0",
    )
    parser.add_argument(
        "--allow-missing-title",
        action="store_true",
        help="允许缺失论文题目但仍要求关键词完整",
    )
    parser.add_argument(
        "--requirements-json",
        default="output/work/客户诉求.json",
        help="客户诉求 JSON 路径（契约校验）",
    )
    parser.add_argument(
        "--check-contract",
        action="store_true",
        help="校验客户诉求 JSON 契约字段",
    )
    parser.add_argument(
        "--strict-contract",
        action="store_true",
        help="契约校验失败时返回非 0",
    )
    return parser.parse_args()


def split_sections(lines: List[str]) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
    preamble: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    current_heading: Optional[str] = None
    current_lines: List[str] = []
    for line in lines:
        if line.startswith("## "):
            if current_heading is None:
                preamble = current_lines
            else:
                sections.append((current_heading, current_lines))
            current_heading = line.strip()
            current_lines = []
            continue
        current_lines.append(line)
    if current_heading is None:
        preamble = current_lines
    else:
        sections.append((current_heading, current_lines))
    return preamble, sections


def list_input_files(input_dir: Path) -> List[str]:
    if not input_dir.exists():
        return []
    files: List[str] = []
    for path in sorted(input_dir.rglob("*")):
        if path.is_file():
            files.append(path.as_posix())
    return files


def split_keywords(value: str) -> List[str]:
    if not value:
        return []
    parts = re.split(r"[、,，;；/|]+", value)
    return [part.strip() for part in parts if part.strip()]


def extract_keywords_from_markdown(content: str) -> Tuple[List[str], List[str]]:
    zh_keywords: List[str] = []
    en_keywords: List[str] = []
    current: Optional[str] = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if "中文关键词" in lower:
            match = re.search(r"[:：]\s*(.+)$", line)
            if match:
                zh_keywords.extend(split_keywords(match.group(1)))
                current = None
                continue
            current = "zh"
            continue
        if "英文关键词" in lower:
            match = re.search(r"[:：]\s*(.+)$", line)
            if match:
                en_keywords.extend(split_keywords(match.group(1)))
                current = None
                continue
            current = "en"
            continue
        if line.startswith("#") and "关键词" not in lower:
            current = None
            continue
        if current and (line.startswith("-") or line.startswith("*")):
            content_line = line.lstrip("-*").strip()
            keywords_line = split_keywords(content_line)
            target = zh_keywords if current == "zh" else en_keywords
            target.extend(keywords_line)
            continue
    return zh_keywords, en_keywords


def collect_keywords_from_input_dir(path: Path) -> Tuple[List[str], List[str]]:
    zh_keywords: List[str] = []
    en_keywords: List[str] = []
    if not path.exists():
        return zh_keywords, en_keywords
    for candidate in path.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in {".md", ".txt", ".yaml", ".yml"}:
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
        except Exception:
            continue
        file_zh, file_en = extract_keywords_from_markdown(content)
        zh_keywords.extend(file_zh)
        en_keywords.extend(file_en)
    return zh_keywords, en_keywords


def dedupe_keywords(items: Iterable[str]) -> List[str]:
    seen = set()
    normalized: List[str] = []
    for item in items:
        norm = item.strip()
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(norm)
    return normalized


def is_placeholder(value: str) -> bool:
    return value.strip() in PLACEHOLDER_VALUES


def ensure_field(
    lines: List[str],
    field: str,
    fallback_value: str,
) -> Tuple[List[str], str]:
    pattern = re.compile(rf"^-\s*{re.escape(field)}\s*[:：]\s*(.*)$")
    for idx, line in enumerate(lines):
        match = pattern.match(line.strip())
        if not match:
            continue
        current_value = match.group(1).strip()
        if current_value and not is_placeholder(current_value):
            return lines, current_value
        lines[idx] = f"- {field}：{fallback_value}"
        return lines, fallback_value
    lines.append(f"- {field}：{fallback_value}")
    return lines, fallback_value


def ensure_basic_info_section(
    lines: List[str], input_files: List[str]
) -> Tuple[List[str], Dict[str, str]]:
    values: Dict[str, str] = {}
    for field in REQUIRED_FIELDS.get("## 客户基本信息", []):
        if field == "现有材料（路径）":
            fallback = "; ".join(input_files) if input_files else "未提供"
        else:
            fallback = "待确认"
        lines, value = ensure_field(lines, field, fallback)
        values[field] = value
    return lines, values


def ensure_keywords_section(
    lines: List[str], keywords_from_input: Tuple[List[str], List[str]]
) -> Tuple[List[str], Dict[str, str]]:
    values: Dict[str, str] = {}
    zh_keywords, en_keywords = keywords_from_input

    for field in REQUIRED_FIELDS.get("## 关键词", []):
        fallback = "待确认"
        if field == "中文关键词" and zh_keywords:
            fallback = "，".join(dedupe_keywords(zh_keywords))
        if field == "英文关键词" and en_keywords:
            fallback = ", ".join(dedupe_keywords(en_keywords))
        lines, value = ensure_field(lines, field, fallback)
        values[field] = value

    return lines, values


def ensure_scope_section(lines: List[str]) -> Tuple[List[str], Dict[str, str]]:
    values: Dict[str, str] = {}
    for field in REQUIRED_FIELDS.get("## 研究范围与边界", []):
        lines, value = ensure_field(lines, field, "待确认")
        values[field] = value
    return lines, values


def ensure_checklist_section(lines: List[str]) -> List[str]:
    required_markers = ["**必须做**", "**禁止做**", "**可选加分项**"]
    for marker in required_markers:
        if any(marker in line for line in lines):
            continue
        lines.append(marker)
        lines.append("- ")
    return lines


def update_missing_section(
    sections: Dict[str, List[str]], missing_fields: List[str]
) -> None:
    if not missing_fields:
        return
    content = [""] + [f"- {field}" for field in missing_fields]
    sections["## 缺失项清单"] = content


def get_nested_value(data: Dict[str, object], dotted_path: str) -> object:
    current: object = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def is_empty_contract_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return is_placeholder(value)
    if isinstance(value, list):
        return len(value) == 0
    return False


def validate_contract_json(json_path: Path) -> List[str]:
    if not json_path.exists():
        return [f"JSON文件不存在: {json_path}"]
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"JSON解析失败: {exc}"]

    if not isinstance(payload, dict):
        return ["JSON根节点必须为对象"]

    missing: List[str] = []
    for label, path in CONTRACT_REQUIRED_JSON_PATHS:
        value = get_nested_value(payload, path)
        if is_empty_contract_value(value):
            missing.append(label)
    return missing


def main() -> int:
    args = parse_args()
    requirements_path = Path(args.requirements)
    input_dir = Path(args.input_dir)
    input_files = list_input_files(input_dir)

    if requirements_path.exists():
        original_lines = requirements_path.read_text(encoding="utf-8").splitlines()
    else:
        original_lines = ["# 客户诉求", ""]

    preamble, sections_list = split_sections(original_lines)
    section_map = {heading: lines for heading, lines in sections_list}
    original_order = [heading for heading, _ in sections_list]

    if not any(line.startswith("# 客户诉求") for line in preamble):
        preamble = ["# 客户诉求", ""] + preamble

    keywords_from_input = collect_keywords_from_input_dir(input_dir)
    field_values: Dict[str, str] = {}

    for heading in REQUIRED_SECTION_ORDER:
        if heading not in section_map:
            section_map[heading] = DEFAULT_SECTION_LINES[heading].copy()
            original_order.append(heading)

    # Ensure required fields
    if "## 客户基本信息" in section_map:
        updated, values = ensure_basic_info_section(
            section_map["## 客户基本信息"],
            input_files,
        )
        section_map["## 客户基本信息"] = updated
        field_values.update(values)

    if "## 研究范围与边界" in section_map:
        updated, values = ensure_scope_section(section_map["## 研究范围与边界"])
        section_map["## 研究范围与边界"] = updated
        field_values.update(values)

    if "## 关键词" in section_map:
        updated, values = ensure_keywords_section(
            section_map["## 关键词"],
            keywords_from_input,
        )
        section_map["## 关键词"] = updated
        field_values.update(values)

    if "## 明确要求清单" in section_map:
        section_map["## 明确要求清单"] = ensure_checklist_section(
            section_map["## 明确要求清单"]
        )

    # Remove existing missing list before regenerating
    if "## 缺失项清单" in section_map:
        section_map.pop("## 缺失项清单", None)
        original_order = [h for h in original_order if h != "## 缺失项清单"]

    missing_fields = [
        field
        for field, value in field_values.items()
        if is_placeholder(value)
    ]
    update_missing_section(section_map, missing_fields)
    if "## 缺失项清单" in section_map:
        original_order.append("## 缺失项清单")

    output_lines: List[str] = []
    output_lines.extend(preamble)
    for heading in original_order:
        if heading not in section_map:
            continue
        if output_lines and output_lines[-1].strip():
            output_lines.append("")
        output_lines.append(heading)
        output_lines.extend(section_map[heading])

    requirements_path.parent.mkdir(parents=True, exist_ok=True)
    requirements_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")

    if missing_fields:
        print("⚠️ 缺失项清单:")
        for field in missing_fields:
            print(f"- {field}")
    else:
        print("✅ 客户诉求结构完整，未发现缺失字段。")

    contract_missing: List[str] = []
    if args.check_contract:
        contract_missing = validate_contract_json(Path(args.requirements_json))
        if contract_missing:
            print("⚠️ 契约校验缺失项:")
            for item in contract_missing:
                print(f"- {item}")
        else:
            print("✅ 客户诉求 JSON 契约校验通过。")

    critical_fields = set(CRITICAL_FIELDS)
    if args.allow_missing_title:
        critical_fields.discard("论文题目")

    if args.strict_contract and contract_missing:
        return 1
    if not args.allow_missing and critical_fields.intersection(missing_fields):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
