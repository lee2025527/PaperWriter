#!/usr/bin/env python3
"""Validate and repair output/work/prompt.md based on template and inputs."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence


PLACEHOLDER_MARKERS = ["[INSERT", "[待补充参考文献列表]"]
REQUIRED_HEADINGS = [
    "## 1. 角色设定",
    "## 2. 项目核心信息",
    "### 2.1 论文题目",
    "### 2.2 关键参数与要求",
    "## 3. 参考文献库",
    "## 4. 写作铁律",
    "## 5. 其他",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate output/work/prompt.md against template and inputs."
    )
    parser.add_argument(
        "--template",
        default="templates/prompt_template.md",
        help="Prompt 模板路径",
    )
    parser.add_argument(
        "--requirements",
        default="output/work/客户诉求.md",
        help="客户诉求路径",
    )
    parser.add_argument(
        "--literature",
        default="output/work/文献详细列表.md",
        help="文献详细列表路径",
    )
    parser.add_argument(
        "--rules",
        default="Universal_Writing_Rules.md",
        help="写作规则路径",
    )
    parser.add_argument(
        "--output",
        default="output/work/prompt.md",
        help="Prompt 输出路径",
    )
    parser.add_argument(
        "--no-fix",
        action="store_true",
        help="只检查不自动修复",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def extract_line(patterns: Sequence[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def parse_requirements(path: Path) -> Dict[str, str]:
    text = read_text(path)
    return {
        "title_zh": extract_line(
            [r"-\s*(?:论文题目|题目)[:：]\s*(.+)"], text
        ),
        "major": extract_line(
            [r"-\s*(?:专业/方向|专业|研究方向)[:：]\s*(.+)"], text
        ),
        "word_count": extract_line([r"-\s*字数[:：]\s*(.+)"], text),
        "plagiarism": extract_line(
            [r"-\s*(?:查重/重复率要求|查重要求)[:：]\s*(.+)"], text
        ),
        "aigc": extract_line(
            [r"-\s*(?:AIGC/AI 检测要求|AIGC要求|AIGC)[:：]\s*(.+)"], text
        ),
    }


def parse_references(path: Path) -> List[str]:
    text = read_text(path)
    marker = "## B. GB/T7714-2015 引用列表区"
    if marker not in text:
        return []
    after = text.split(marker, 1)[1]
    lines = [line.strip() for line in after.splitlines() if line.strip()]
    return [line for line in lines if line.startswith("[")]


def parse_prompt_references(prompt_text: str) -> List[str]:
    marker = "## 3. 参考文献库"
    if marker not in prompt_text:
        return []
    after = prompt_text.split(marker, 1)[1]
    end_index = after.find("\n## ")
    section = after[:end_index] if end_index != -1 else after
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    return [line for line in lines if line.startswith("[")]


def normalize_reference_line(line: str) -> str:
    line = re.sub(r"^\[\d+\]\s*", "", line).strip()
    return re.sub(r"\s+", " ", line)


def extract_prompt_fields(text: str) -> Dict[str, str]:
    return {
        "title_zh": extract_line([r"\*\*中文\*\*:\s*\*\*(.+?)\*\*"], text),
        "title_en": extract_line([r"\*\*英文\*\*:\s*\*\*(.+?)\*\*"], text),
        "word_count": extract_line(
            [r"\*\*字数要求\*\*:\s*全文约\s*([^\s]+)\s*字"], text
        ),
        "plagiarism": extract_line(
            [r"\*\*查重红线\*\*:\s*\*\*<\s*([^%]+)%"], text
        ),
        "aigc": extract_line(
            [r"\*\*AIGC红线\*\*:\s*\*\*<\s*([^%]+)%"], text
        ),
        "major": extract_line(
            [r"\*\*身份\*\*:\s*[^“\"]*[“\"]([^”\"]+)[”\"]"], text
        ),
    }


def normalize_digits(value: str) -> str:
    match = re.search(r"(\d+)", value)
    return match.group(1) if match else value.strip()


def check_prompt(
    prompt_text: str,
    requirements: Dict[str, str],
    literature_refs: List[str],
    rules_path: Path,
) -> List[str]:
    issues: List[str] = []

    for heading in REQUIRED_HEADINGS:
        if heading not in prompt_text:
            issues.append(f"缺少标题: {heading}")

    for marker in PLACEHOLDER_MARKERS:
        if marker in prompt_text:
            issues.append(f"存在占位符/待确认提示: {marker}")
            break

    prompt_fields = extract_prompt_fields(prompt_text)
    if requirements.get("title_zh"):
        if requirements["title_zh"] not in prompt_text:
            issues.append("Prompt 未体现客户题目")

    if requirements.get("major"):
        if requirements["major"] not in prompt_text:
            issues.append("Prompt 未体现客户专业/方向")

    if requirements.get("word_count"):
        req_wc = normalize_digits(requirements["word_count"])
        prompt_wc = normalize_digits(prompt_fields.get("word_count", ""))
        if req_wc and not prompt_wc:
            issues.append("Prompt 未填写字数要求")
        elif req_wc and prompt_wc and req_wc != prompt_wc:
            issues.append("Prompt 字数要求与客户诉求不一致")

    if requirements.get("plagiarism"):
        req_plag = normalize_digits(requirements["plagiarism"])
        prompt_plag = normalize_digits(prompt_fields.get("plagiarism", ""))
        if req_plag and not prompt_plag:
            issues.append("Prompt 未填写查重红线")
        elif req_plag and prompt_plag and req_plag != prompt_plag:
            issues.append("Prompt 查重红线与客户诉求不一致")

    if requirements.get("aigc"):
        req_aigc = normalize_digits(requirements["aigc"])
        prompt_aigc = normalize_digits(prompt_fields.get("aigc", ""))
        if req_aigc and not prompt_aigc:
            issues.append("Prompt 未填写 AIGC 红线")
        elif req_aigc and prompt_aigc and req_aigc != prompt_aigc:
            issues.append("Prompt AIGC 红线与客户诉求不一致")

    if rules_path.exists() and str(rules_path) not in prompt_text:
        issues.append("Prompt 未列出 Universal_Writing_Rules.md")

    prompt_refs = parse_prompt_references(prompt_text)
    if not literature_refs:
        issues.append("文献详细列表缺少引用列表区")
    else:
        if not prompt_refs:
            issues.append("Prompt 未插入参考文献列表")
        else:
            prompt_norm = {normalize_reference_line(r) for r in prompt_refs}
            lit_norm = {normalize_reference_line(r) for r in literature_refs}
            if not lit_norm.issubset(prompt_norm):
                issues.append("Prompt 参考文献与文献详细列表不一致")

    return issues


def run_build_prompt(args: argparse.Namespace) -> bool:
    cmd = [
        sys.executable,
        "skills/writing-prompt-builder/scripts/build_prompt.py",
        "--template",
        args.template,
        "--requirements",
        args.requirements,
        "--literature",
        args.literature,
        "--rules",
        args.rules,
        "--output",
        args.output,
    ]
    result = subprocess.run(cmd)
    return result.returncode == 0


def main() -> int:
    args = parse_args()
    prompt_path = Path(args.output)
    prompt_text = read_text(prompt_path)
    requirements = parse_requirements(Path(args.requirements))
    literature_refs = parse_references(Path(args.literature))
    rules_path = Path(args.rules)

    issues = check_prompt(prompt_text, requirements, literature_refs, rules_path)
    if issues and not args.no_fix:
        print("⚠️ Prompt 校验失败，尝试重新生成...")
        if run_build_prompt(args):
            prompt_text = read_text(prompt_path)
            issues = check_prompt(prompt_text, requirements, literature_refs, rules_path)
        else:
            issues.append("自动修复失败：build_prompt 执行失败")

    if issues:
        print("❌ Prompt 校验未通过：")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("✅ Prompt 校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
