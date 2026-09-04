#!/usr/bin/env python3
"""Build project prompt.md from template and project inputs."""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build output/work/prompt.md from template and project inputs."
    )
    parser.add_argument(
        "--template",
        default="templates/prompt_template.md",
        help="Path to prompt template",
    )
    parser.add_argument(
        "--requirements",
        default="output/work/客户诉求.md",
        help="Path to 客户诉求.md",
    )
    parser.add_argument(
        "--literature",
        default="output/work/文献详细列表.md",
        help="Path to 文献详细列表.md",
    )
    parser.add_argument(
        "--rules",
        default="Universal_Writing_Rules.md",
        help="Path to Universal_Writing_Rules.md",
    )
    parser.add_argument(
        "--output",
        default="output/work/prompt.md",
        help="Output prompt path",
    )
    parser.add_argument("--title-zh", default="", help="Override Chinese title")
    parser.add_argument("--title-en", default="", help="Override English title")
    parser.add_argument("--major", default="", help="Override major")
    parser.add_argument("--word-count", default="", help="Override word count")
    parser.add_argument("--plagiarism", default="", help="Override plagiarism percent")
    parser.add_argument("--aigc", default="", help="Override AIGC percent")
    parser.add_argument(
        "--core-function",
        default="",
        help="Override core function description",
    )
    parser.add_argument(
        "--key-tech",
        default="",
        help="Comma-separated key technologies",
    )
    return parser.parse_args()


def extract_line(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return None


def parse_requirements(path: Path) -> dict:
    data = {
        "title_zh": "",
        "major": "",
        "word_count": "",
        "plagiarism": "",
        "aigc": "",
        "keywords_zh": [],
        "keywords_en": [],
        "must_do": [],
    }
    if not path.exists():
        return data

    text = path.read_text(encoding="utf-8")
    data["title_zh"] = extract_line(r"-\s*(?:论文题目|题目)[:：](.+)", text) or ""
    data["major"] = extract_line(
        r"-\s*(?:专业/方向|专业|研究方向)[:：](.+)", text
    ) or ""
    data["word_count"] = extract_line(r"-\s*字数[:：](.+)", text) or ""
    data["plagiarism"] = extract_line(
        r"-\s*(?:查重/重复率要求|查重要求)[:：](.+)", text
    ) or ""
    data["aigc"] = extract_line(
        r"-\s*(?:AIGC/AI 检测要求|AIGC要求|AIGC)[:：](.+)", text
    ) or ""

    keywords_zh = extract_line(r"-\s*中文关键词：(.+)", text) or ""
    keywords_en = extract_line(r"-\s*英文关键词：(.+)", text) or ""

    data["keywords_zh"] = [k.strip() for k in re.split(r"[；;，,]", keywords_zh) if k.strip()]
    data["keywords_en"] = [k.strip() for k in re.split(r"[；;，,]", keywords_en) if k.strip()]

    # Collect must-do bullets
    must_do_section = re.search(r"## 明确要求清单([\s\S]+?)##", text)
    if must_do_section:
        for line in must_do_section.group(1).splitlines():
            line = line.strip()
            if line.startswith("-") and "必须做" not in line:
                data["must_do"].append(line.lstrip("- "))

    return data


def parse_references(path: Path) -> List[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    marker = "## B. GB/T7714-2015 引用列表区"
    if marker not in text:
        return []
    after = text.split(marker, 1)[1]
    lines = [line.strip() for line in after.splitlines() if line.strip()]
    refs = [line for line in lines if line.startswith("[")]
    return refs


def normalize_percent(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"(\d+(\.\d+)?)", value)
    return match.group(1) if match else value.strip()


def normalize_word_count(value: str) -> str:
    if not value:
        return ""
    match = re.search(r"(\d+)", value)
    return match.group(1) if match else value.strip()


def replace_placeholder_regex(text: str, pattern: str, value: str) -> str:
    return re.sub(pattern, value, text)


def replace_first(text: str, old: str, new: str) -> str:
    return text.replace(old, new, 1)


def main() -> int:
    args = parse_args()
    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")

    requirements = parse_requirements(Path(args.requirements))
    references = parse_references(Path(args.literature))

    title_zh = args.title_zh or requirements.get("title_zh") or "待确认"
    title_en = args.title_en or "待确认（如需英文题目请补充）"
    major = args.major or requirements.get("major") or "待确认"
    word_count = normalize_word_count(
        args.word_count or requirements.get("word_count") or ""
    ) or "待确认"
    plagiarism = normalize_percent(
        args.plagiarism or requirements.get("plagiarism") or ""
    ) or "待确认"
    aigc = normalize_percent(args.aigc or requirements.get("aigc") or "") or "5"

    if not args.core_function:
        must_do = requirements.get("must_do") or []
        if must_do:
            core_function = " → ".join(must_do[:3])
        else:
            core_function = "以客户诉求为准"
    else:
        core_function = args.core_function

    key_tech = []
    if args.key_tech:
        key_tech = [k.strip() for k in args.key_tech.split(",") if k.strip()]
    elif requirements.get("keywords_zh"):
        key_tech = requirements["keywords_zh"][:3]

    while len(key_tech) < 3:
        key_tech.append("待补充")

    template = template_path.read_text(encoding="utf-8")

    # Replace placeholders
    template = replace_placeholder_regex(
        template, r"\[INSERT UNIVERSITY LEVEL[^\]]*\]", "省属重点高校"
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT MAJOR[^\]]*\]", major
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT SKILL 1[^\]]*\]", key_tech[0]
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT SKILL 2[^\]]*\]", key_tech[1]
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT SKILL 3[^\]]*\]", key_tech[2]
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT CHINESE TITLE[^\]]*\]", title_zh
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT ENGLISH TITLE[^\]]*\]", title_en
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT CORE FUNCTION DESCRIPTION[^\]]*\]", core_function
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT KEY TECH 1[^\]]*\]", key_tech[0]
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT KEY TECH 2[^\]]*\]", key_tech[1]
    )
    template = replace_placeholder_regex(
        template, r"\[INSERT WORD COUNT[^\]]*\]", word_count
    )

    # Replace percentages sequentially
    template = replace_first(template, "[INSERT PERCENTAGE]", plagiarism)
    template = replace_first(template, "[INSERT PERCENTAGE]", aigc)

    # Insert references
    if references:
        ref_block = "\n".join(references)
    else:
        ref_block = "[待补充参考文献列表]"

    template = template.replace(
        "[1] [INSERT ENGLISH REF 1]\n[2] [INSERT ENGLISH REF 2]\n...",
        "- 无（本项目以中文文献为主）",
    )
    template = template.replace(
        "[6] [INSERT CHINESE REF 1]\n[7] [INSERT CHINESE REF 2]\n...",
        ref_block,
    )

    # Append required material list
    must_read = []
    for path in [
        Path(args.requirements),
        Path(args.literature),
        Path("output/work/对标论文结构与写作标准解析.md"),
        Path(args.rules),
    ]:
        if path.exists():
            must_read.append(f"- {path}")

    if must_read:
        template += "\n\n## 6. 写作前必读材料\n\n" + "\n".join(must_read)

    template += (
        "\n\n## 7. 写作原则摘要\n\n"
        "- 严禁编造文献与数据，引用必须可核验。\n"
        "- 拒绝 AI 腔，保持真人化叙述与工程逻辑。\n"
        "- 若 input 与规则冲突，以 input 为准。\n"
        "- 全文结构与引用编号必须一致。\n"
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template, encoding="utf-8")
    print(f"written {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
