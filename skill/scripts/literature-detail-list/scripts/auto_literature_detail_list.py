#!/usr/bin/env python3
"""
Auto-build literature detail list:
1) If input/ contains existing references, format them into output/work/文献详细列表.md.
2) Otherwise run the local literature pipeline and filter outputs as usual.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree as ET


REF_HEADING_RE = re.compile(
    r"^(#+\s*)?(参考文献|参考资料|文献列表|references|bibliography)\b",
    re.IGNORECASE,
)
STOP_HEADING_RE = re.compile(
    r"^(#+\s*)?(致谢|附录|声明|目录|摘要|abstract|acknowledg(e)?ments|appendix)\b",
    re.IGNORECASE,
)
REF_START_RE = re.compile(r"^\s*(\[\d+\]|\(?\d+\)?[.)])\s+")
YEAR_RE = re.compile(r"(19|20)\d{2}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-build 文献详细列表: prefer existing input references, "
        "otherwise run search pipeline and filter.",
    )
    parser.add_argument("--input-dir", default="input", help="Input directory")
    parser.add_argument(
        "--demand-file",
        default="output/work/客户诉求.md",
        help="客户诉求文件路径",
    )
    parser.add_argument(
        "--output",
        default="output/work/文献详细列表.md",
        help="输出文献详细列表路径",
    )
    parser.add_argument(
        "--intermediate-dir",
        default="output/work/文献检索中间产物",
        help="检索中间产物目录",
    )
    parser.add_argument(
        "--pipeline-prefix",
        default="文献检索结果",
        help="检索中间产物文件名前缀",
    )
    parser.add_argument("--topic", default="", help="论文题目 (可选覆盖)")
    parser.add_argument("--keywords-zh", default="", help="中文关键词 (可选覆盖)")
    parser.add_argument("--keywords-en", default="", help="英文关键词 (可选覆盖)")
    parser.add_argument("--major", default="", help="专业/方向 (可选覆盖)")
    parser.add_argument("--max", type=int, default=18, help="检索最大结果数")
    parser.add_argument(
        "--keep-all-results",
        action="store_true",
        help="保留全部检索结果",
    )
    parser.add_argument("--recent-years", type=int, default=5, help="近年限制")
    parser.add_argument(
        "--min-abstract-length",
        type=int,
        default=120,
        help="最小摘要长度",
    )
    parser.add_argument("--min-count", type=int, default=10, help="目标数量")
    parser.add_argument(
        "--strict-filter",
        action="store_true",
        help="启用严格筛选",
    )
    parser.add_argument(
        "--no-link-check",
        action="store_true",
        help="禁用链接校验",
    )
    parser.add_argument(
        "--exclude-scholar-snippet",
        action="store_true",
        help="严格模式下排除 scholar snippet 摘要",
    )
    return parser.parse_args()


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def extract_docx_paragraphs(path: Path) -> List[str]:
    try:
        with zipfile.ZipFile(path) as zf:
            xml_bytes = zf.read("word/document.xml")
    except Exception:
        return []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: List[str] = []
    for para in root.findall(".//w:p", ns):
        texts = [node.text for node in para.findall(".//w:t", ns) if node.text]
        if texts:
            paragraphs.append("".join(texts))
    return paragraphs


def strip_bullets(line: str) -> str:
    return line.lstrip("-*•").strip()


def normalize_reference_line(line: str) -> str:
    line = strip_bullets(line)
    line = re.sub(r"^\s*\[\d+\]\s*", "", line)
    line = re.sub(r"^\s*\(?\d+\)?[.)]\s*", "", line)
    return line.strip()


def has_numbered_reference(line: str) -> bool:
    return bool(REF_START_RE.match(line.strip()))


def has_year(line: str) -> bool:
    return bool(YEAR_RE.search(line))


def is_heading_like(line: str) -> bool:
    if line.startswith("#"):
        return True
    if re.match(r"^第[一二三四五六七八九十0-9]+章", line):
        return True
    return bool(STOP_HEADING_RE.match(line))


def extract_references_from_lines(lines: Iterable[str]) -> List[str]:
    section_lines: List[str] = []
    in_refs = False
    found_heading = False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if REF_HEADING_RE.match(line):
            in_refs = True
            found_heading = True
            continue
        if in_refs and STOP_HEADING_RE.match(line):
            break
        if in_refs:
            section_lines.append(strip_bullets(line))

    if found_heading and section_lines:
        refs: List[str] = []
        for line in section_lines:
            if REF_START_RE.match(line):
                refs.append(line)
            elif refs:
                refs[-1] = f"{refs[-1]} {line}"
        if refs:
            return refs

        # If no numbered refs, fall back to lines containing year patterns.
        year_refs = [line for line in section_lines if re.search(r"(19|20)\d{2}", line)]
        if year_refs:
            return year_refs

    # Fallback: scan for numbered references without explicit heading
    fallback_refs: List[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or REF_HEADING_RE.match(line):
            continue
        line = strip_bullets(line)
        if REF_START_RE.match(line):
            fallback_refs.append(line)
        elif fallback_refs and not is_heading_like(line):
            fallback_refs[-1] = f"{fallback_refs[-1]} {line}"

    return fallback_refs


def collect_references_from_file(path: Path) -> List[str]:
    if path.suffix.lower() == ".docx":
        lines = extract_docx_paragraphs(path)
        return extract_references_from_lines(lines)
    if path.suffix.lower() in {".md", ".txt"}:
        content = read_text_file(path)
        return extract_references_from_lines(content.splitlines())
    return []


def scan_input_for_references(input_dir: Path) -> Tuple[List[Dict[str, str]], Counter]:
    refs: List[Dict[str, str]] = []
    counts: Counter = Counter()
    seen: set[str] = set()
    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".txt", ".docx"}:
            continue
        extracted = collect_references_from_file(path)
        if not extracted:
            continue
        for raw in extracted:
            norm = normalize_reference_line(raw)
            if not norm:
                continue
            key = re.sub(r"\s+", " ", norm).lower()
            if key in seen:
                continue
            seen.add(key)
            refs.append({"raw": raw.strip(), "norm": norm, "source": path.as_posix()})
            counts[path.as_posix()] += 1
    return refs, counts


def write_existing_references_output(
    output_path: Path, refs: List[Dict[str, str]], counts: Counter
) -> None:
    lines: List[str] = []
    lines.append("# 文献详细列表（客户提供版）")
    lines.append("")
    lines.append("## 来源说明")
    lines.append("- 检测到客户已提供参考文献，跳过 API 检索。")
    for source, count in counts.items():
        lines.append(f"- {source}: {count} 条")
    lines.append("")
    lines.append("## A. 文献详细信息区")
    lines.append("")
    for idx, ref in enumerate(refs, 1):
        title = ref["norm"]
        if len(title) > 80:
            title = f"{title[:77]}..."
        lines.append(f"### {idx}. {title}")
        lines.append("- **来源**: 客户提供")
        lines.append(f"- **来源文件**: {ref['source']}")
        lines.append(f"- **原始条目**: {ref['raw']}")
        lines.append("- **摘要**: N/A")
        lines.append("")
    lines.append("## B. GB/T7714-2015 引用列表区")
    lines.append("")
    for idx, ref in enumerate(refs, 1):
        lines.append(f"[{idx}] {ref['norm']}")
    lines.append("")
    lines.append("## 数量校验")
    lines.append(f"- **总计**: {len(refs)} 篇")
    lines.append("- **说明**: 仅整理客户提供文献，未执行检索。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


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


def split_keywords(value: str) -> List[str]:
    if not value:
        return []
    parts = re.split(r"[、,，;；/|]+", value)
    return [part.strip() for part in parts if part.strip()]


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
        content = read_text_file(candidate)
        file_zh, file_en = extract_keywords_from_markdown(content)
        zh_keywords.extend(file_zh)
        en_keywords.extend(file_en)
    return zh_keywords, en_keywords


def extract_topic_and_major(content: str) -> Tuple[str, str]:
    topic = ""
    major = ""
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not topic:
            match = re.search(r"(论文题目|题目)\s*[:：]\s*(.+)$", line)
            if match:
                topic = match.group(2).strip()
        if not major:
            match = re.search(r"(专业/方向|专业|研究方向)\s*[:：]\s*(.+)$", line)
            if match:
                major = match.group(2).strip()
        if topic and major:
            break
    return topic, major


def run_command(cmd: List[str], label: str) -> None:
    print(f"▶ {label}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def run_pipeline_and_filter(
    args: argparse.Namespace,
    topic: str,
    keywords_zh: List[str],
    keywords_en: List[str],
    major: str,
) -> None:
    pipeline_script = Path("tools") / "文献检索增强工具" / "run_literature_pipeline.py"
    filter_script = (
        Path("skills")
        / "literature-detail-list"
        / "scripts"
        / "filter_literature.py"
    )

    if not pipeline_script.exists():
        raise SystemExit("❌ 未找到文献检索工具脚本")

    if not topic or not keywords_zh or not keywords_en:
        raise SystemExit("❌ 缺少题目或中英文关键词，请补充客户诉求。")

    pipeline_cmd = [
        sys.executable,
        str(pipeline_script),
        "--topic",
        topic,
        "--keywords-zh",
        ",".join(keywords_zh),
        "--keywords-en",
        ",".join(keywords_en),
        "--major",
        major,
        "--max",
        str(args.max),
        "--output",
        args.pipeline_prefix,
    ]
    if args.keep_all_results:
        pipeline_cmd.append("--keep-all-results")

    run_command(pipeline_cmd, "Step2 Pipeline: 文献检索与摘要增强")

    intermediate_dir = Path(args.intermediate_dir)
    zh_stage3 = intermediate_dir / f"{args.pipeline_prefix}_zh_openalex_stage3.json"
    en_stage3 = intermediate_dir / f"{args.pipeline_prefix}_en_openalex_stage3.json"

    input_paths = [zh_stage3]
    if en_stage3.exists():
        input_paths.append(en_stage3)

    filter_cmd = [
        sys.executable,
        str(filter_script),
        *[str(p) for p in input_paths],
        "--output",
        args.output,
        "--demand-file",
        args.demand_file,
        "--input-dir",
        args.input_dir,
        "--topic",
        topic,
        "--recent-years",
        str(args.recent_years),
        "--min-abstract-length",
        str(args.min_abstract_length),
        "--min-count",
        str(args.min_count),
    ]
    if args.strict_filter:
        filter_cmd.append("--strict-filter")
    if args.no_link_check:
        filter_cmd.append("--no-link-check")
    if args.exclude_scholar_snippet:
        filter_cmd.append("--exclude-scholar-snippet")

    run_command(filter_cmd, "Step2 Filter: 生成文献详细列表")


def main() -> int:
    args = parse_args()
    args.pipeline_prefix = Path(args.pipeline_prefix).name or args.pipeline_prefix
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    refs, counts = scan_input_for_references(input_dir)
    qualified_refs = [
        ref for ref in refs if has_numbered_reference(ref["raw"]) and has_year(ref["raw"])
    ]
    if qualified_refs:
        print(
            "✅ 检测到客户参考文献列表（含编号+年份条目），"
            f"共 {len(refs)} 条，跳过检索。"
        )
        write_existing_references_output(output_path, refs, counts)
        print(f"✅ 输出完成: {output_path}")
        return 0
    if refs:
        print(
            "⚠️ 检测到疑似参考文献，但未找到“编号+年份”条目，"
            "将继续执行检索流程。"
        )

    demand_path = Path(args.demand_file)
    if not demand_path.exists():
        raise SystemExit("❌ 未找到客户诉求文件，无法提取题目与关键词。")

    demand_text = read_text_file(demand_path)
    topic, major = extract_topic_and_major(demand_text)
    zh_from_demand, en_from_demand = extract_keywords_from_markdown(demand_text)
    zh_from_input: List[str] = []
    en_from_input: List[str] = []
    if not zh_from_demand and not en_from_demand:
        zh_from_input, en_from_input = collect_keywords_from_input_dir(input_dir)

    keywords_zh = dedupe_keywords(
        split_keywords(args.keywords_zh) + zh_from_demand + zh_from_input
    )
    keywords_en = dedupe_keywords(
        split_keywords(args.keywords_en) + en_from_demand + en_from_input
    )

    if args.topic:
        topic = args.topic
    if args.major:
        major = args.major

    run_pipeline_and_filter(args, topic, keywords_zh, keywords_en, major)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
