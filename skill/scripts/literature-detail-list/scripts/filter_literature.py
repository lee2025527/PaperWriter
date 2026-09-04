#!/usr/bin/env python3
"""
Filter literature JSON outputs into a detailed list markdown with intelligent recovery.

Enhanced features:
- Automatic recovery when filtered papers < 7
- Relaxed filtering criteria for recovery phase
- Only requirement: topic relevance (year, abstract length, source don't matter)
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.error import HTTPError
from urllib.request import Request, urlopen


# Reuse utility functions from original script
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter literature JSON results with intelligent recovery."
    )
    parser.add_argument("inputs", nargs="+", help="*_openalex_stage3.json files")
    parser.add_argument(
        "--output",
        default="output/work/文献详细列表.md",
        help="Output markdown path",
    )
    parser.add_argument(
        "--demand-file",
        default="output/work/客户诉求.md",
        help="Path containing client keywords",
    )
    parser.add_argument(
        "--input-dir",
        default="input",
        help="Directory to scan for fallback keyword hints",
    )
    parser.add_argument("--topic", default="", help="Topic to match in title/abstract")
    parser.add_argument(
        "--keywords-zh",
        default="",
        help="Chinese keywords (comma-separated)",
    )
    parser.add_argument(
        "--keywords-en",
        default="",
        help="English keywords (comma-separated)",
    )
    parser.add_argument(
        "--recent-years",
        type=int,
        default=5,
        help="Keep papers within recent N years (default 5)",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=10,
        help="Target count for reference (default 10)",
    )
    parser.add_argument(
        "--allow-english",
        action="store_true",
        help="Include English papers if present",
    )
    parser.add_argument(
        "--no-link-check",
        action="store_true",
        help="Skip link validation",
    )
    parser.add_argument(
        "--min-abstract-length",
        type=int,
        default=120,
        help="Minimum abstract length for strict filtering (default 120)",
    )
    parser.add_argument(
        "--max-abstract-length",
        type=int,
        default=800,
        help="Maximum abstract length",
    )
    parser.add_argument(
        "--exclude-scholar-snippet",
        action="store_true",
        help="Exclude scholar snippet abstracts in strict mode",
    )
    parser.add_argument(
        "--strict-filter",
        action="store_true",
        help="Require year/abstract/link/source checks (disable inclusive mode)",
    )
    parser.add_argument(
        "--recovery-threshold",
        type=int,
        default=7,
        help="Trigger recovery when filtered papers < this number (default 7)",
    )
    parser.add_argument(
        "--disable-recovery",
        action="store_true",
        help="Disable automatic recovery mechanism",
    )
    return parser.parse_args()


def split_keywords(value: str) -> List[str]:
    if not value:
        return []
    parts = re.split(r"[、,，;；/|]+", value)
    return [part.strip() for part in parts if part.strip()]


def split_keyword_line(value: str) -> List[str]:
    return split_keywords(value)


def dedupe_keywords(items: Sequence[str]) -> List[str]:
    seen = set()
    normalized = []
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


def contains_chinese(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def extract_inline_keywords(line: str) -> Optional[List[str]]:
    match = re.search(r"[:：]\s*(.+)$", line)
    if match:
        return split_keyword_line(match.group(1))
    return None


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
            inline = extract_inline_keywords(line)
            if inline:
                zh_keywords.extend(inline)
                current = None
                continue
            current = "zh"
            continue
        if "英文关键词" in lower:
            inline = extract_inline_keywords(line)
            if inline:
                en_keywords.extend(inline)
                current = None
                continue
            current = "en"
            continue
        if line.startswith("#") and "关键词" not in lower:
            current = None
            continue
        if current and (line.startswith("-") or line.startswith("*")):
            content_line = line.lstrip("-*").strip()
            keywords_line = split_keyword_line(content_line)
            target = zh_keywords if current == "zh" else en_keywords
            target.extend(keywords_line)
            continue
    return zh_keywords, en_keywords


def collect_keywords_from_file(path: Path) -> Tuple[List[str], List[str]]:
    if not path.is_file():
        return [], []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return [], []
    return extract_keywords_from_markdown(content)


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
        file_zh, file_en = collect_keywords_from_file(candidate)
        zh_keywords.extend(file_zh)
        en_keywords.extend(file_en)
    return zh_keywords, en_keywords


def clean_abstract(text: str, max_len: int) -> str:
    if not text:
        return "N/A"
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("［", "").replace("］", "").replace("【", "").replace("】", "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "..."
    return text


def is_noise(text: str, min_len: int) -> bool:
    if not text:
        return False
    stripped = text.strip()
    if min_len and len(stripped) < min_len:
        return True
    low = text.lower()
    noise_markers = [
        "espnet",
        "aishell",
        "laborotv",
        "pytorch",
        "asr",
        "asr_train",
        "git clone",
        "config:",
    ]
    if any(m in low for m in noise_markers):
        return True
    if len(re.findall(r"<[^>]+>", text)) > 5:
        return True
    return False


def is_recent(year: Optional[int], recent_years: int) -> bool:
    if not year:
        return False
    current_year = datetime.now().year
    return year >= current_year - recent_years


def match_keywords(text: str, keywords: Iterable[str]) -> bool:
    return any(k in text for k in keywords)


def pick_best_link(paper: Dict) -> str:
    return (
        paper.get("pdf_url")
        or paper.get("oa_pdf_url")
        or paper.get("pdf_source_url")
        or paper.get("url")
        or paper.get("oa_landing_page_url")
        or ""
    )


def unique_in_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def check_url(url: str) -> str:
    if not url:
        return "N/A"
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=12) as resp:
            return str(resp.status)
    except HTTPError as exc:
        return str(exc.code)
    except Exception:
        try:
            req = Request(
                url,
                method="GET",
                headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-1023"},
            )
            with urlopen(req, timeout=12) as resp:
                return str(resp.status)
        except Exception as exc:
            return f"ERR:{type(exc).__name__}"


def load_papers(paths: List[Path]) -> List[Dict]:
    papers: List[Dict] = []
    for path in paths:
        obj = json.loads(path.read_text(encoding="utf-8"))
        papers.extend(obj.get("search_results", {}).get("papers", []))
    return papers


def load_citations(paths: List[Path]) -> List[str]:
    citations: List[str] = []
    for path in paths:
        obj = json.loads(path.read_text(encoding="utf-8"))
        citations.extend(obj.get("search_results", {}).get("formatted_citations", []))
    return citations


def select_papers_strict(
    input_paths: List[Path],
    keywords_zh: List[str],
    keywords_en: List[str],
    allow_english: bool,
    recent_years: int,
    min_abstract_length: int,
    exclude_scholar_snippet: bool,
    no_link_check: bool,
    include_all_related: bool,
) -> List[Dict]:
    """Strict filtering with all criteria applied."""
    allowed_sources = {
        "pdf",
        "html_meta",
        "openalex",
        "scholar_snippet",
        "crossref",
        "semantic_scholar",
        "europe_pmc",
    }
    papers = load_papers(input_paths)

    # Deduplicate by title
    seen = set()
    unique: List[Dict] = []
    for p in papers:
        title = (p.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        unique.append(p)

    selected: List[Dict] = []
    keywords_en_lower = [kw.lower() for kw in keywords_en]
    for p in unique:
        title = p.get("title") or ""
        abstract = p.get("abstract") or p.get("snippet") or ""
        source = p.get("abstract_source") or ""

        if source and source not in allowed_sources and not include_all_related:
            continue
        if not source and not include_all_related:
            continue
        if source == "scholar_snippet" and exclude_scholar_snippet:
            continue

        year = p.get("year")
        recent = is_recent(year, recent_years)
        if not recent and not include_all_related:
            continue

        abstract_stripped = abstract.strip()
        abstract_too_short = (
            min_abstract_length and len(abstract_stripped) < min_abstract_length
        )
        abstract_noise = is_noise(abstract, 0)
        if (abstract_too_short or abstract_noise) and not include_all_related:
            continue

        text = f"{title} {abstract}"
        lower_text = text.lower()
        title_lower = title.lower()
        abstract_lower = abstract.lower()
        match = False
        if keywords_zh and match_keywords(text, keywords_zh):
            match = True
        elif allow_english and keywords_en_lower and match_keywords(
            lower_text, keywords_en_lower
        ):
            match = True
        if not match:
            continue

        matched_zh_title = unique_in_order([kw for kw in keywords_zh if kw in title])
        matched_zh_abstract = unique_in_order(
            [kw for kw in keywords_zh if kw in abstract]
        )
        matched_en_title = []
        matched_en_abstract = []
        if allow_english and keywords_en:
            matched_en_title = unique_in_order(
                [kw for kw in keywords_en if kw.lower() in title_lower]
            )
            matched_en_abstract = unique_in_order(
                [kw for kw in keywords_en if kw.lower() in abstract_lower]
            )

        link = pick_best_link(p)
        if no_link_check:
            status = "unchecked"
        else:
            status = check_url(link)
            if status.startswith("ERR:") and not include_all_related:
                continue
        p["_recent"] = recent
        p["_abstract_usable"] = (
            bool(abstract_stripped) and not abstract_noise and not abstract_too_short
        )
        abstract_issues: List[str] = []
        if not abstract_stripped:
            abstract_issues.append("缺失")
        if abstract_too_short:
            abstract_issues.append("过短")
        if abstract_noise:
            abstract_issues.append("噪声")
        if abstract_issues:
            p["_abstract_issues"] = abstract_issues
        p["_match_title_zh"] = matched_zh_title
        p["_match_abstract_zh"] = matched_zh_abstract
        p["_match_title_en"] = matched_en_title
        p["_match_abstract_en"] = matched_en_abstract
        p["_link_status"] = status
        selected.append(p)

    selected.sort(key=lambda paper: (paper.get("year") or 0, paper.get("enhanced_score") or 0), reverse=True)
    return selected


def expand_keywords_substrings(keywords: List[str]) -> List[str]:
    """
    Expand keywords by extracting common substrings (2-4 chars for Chinese, 2+ words for English).
    This helps match partial mentions in titles/abstracts.
    """
    import re

    expanded = set(keywords)  # Keep original keywords

    for kw in keywords:
        # For Chinese keywords: extract 2-4 character substrings
        if contains_chinese(kw):
            # Extract meaningful substrings (2-4 characters)
            if len(kw) >= 4:
                # Extract 2-char substrings
                for i in range(len(kw) - 1):
                    substr = kw[i:i+2]
                    if substr.strip():
                        expanded.add(substr)
                # Extract 3-char substrings
                if len(kw) >= 5:
                    for i in range(len(kw) - 2):
                        substr = kw[i:i+3]
                        if substr.strip():
                            expanded.add(substr)
                # Extract 4-char substrings
                if len(kw) >= 6:
                    for i in range(len(kw) - 3):
                        substr = kw[i:i+4]
                        if substr.strip():
                            expanded.add(substr)
        # For English keywords: extract individual words
        else:
            words = re.findall(r'\b[a-zA-Z]{2,}\b', kw)
            for word in words:
                expanded.add(word.lower())

    return list(expanded)


def recover_papers_relaxed(
    input_paths: List[Path],
    keywords_zh: List[str],
    keywords_en: List[str],
    allow_english: bool,
    already_selected_titles: set,
) -> List[Dict]:
    """
    Recovery phase: ONLY check topic relevance, ignore ALL other constraints.
    Year, abstract length, source, link status - all ignored.
    Only requirement: must match keywords in title or abstract.
    """
    papers = load_papers(input_paths)

    # Expand keywords for more flexible matching in recovery phase
    expanded_keywords_zh = expand_keywords_substrings(keywords_zh)
    expanded_keywords_en = expand_keywords_substrings(keywords_en)

    # Deduplicate by title
    unique: List[Dict] = []
    for p in papers:
        title = (p.get("title") or "").strip()
        if not title or title in already_selected_titles:
            continue
        unique.append(p)

    recovered: List[Dict] = []
    keywords_en_lower = [kw.lower() for kw in expanded_keywords_en]

    for p in unique:
        title = p.get("title") or ""
        abstract = p.get("abstract") or p.get("snippet") or ""
        year = p.get("year")

        # ONLY check relevance - ignore all other constraints
        text = f"{title} {abstract}"
        lower_text = text.lower()
        title_lower = title.lower()
        abstract_lower = abstract.lower()

        match = False
        if expanded_keywords_zh and match_keywords(text, expanded_keywords_zh):
            match = True
        elif allow_english and keywords_en_lower and match_keywords(
            lower_text, keywords_en_lower
        ):
            match = True

        if not match:
            continue

        # Extract matched keywords for display (use original keywords, not expanded)
        matched_zh_title = unique_in_order([kw for kw in keywords_zh if kw in title])
        matched_zh_abstract = unique_in_order(
            [kw for kw in keywords_zh if kw in abstract]
        )
        matched_en_title = []
        matched_en_abstract = []
        if allow_english and keywords_en:
            matched_en_title = unique_in_order(
                [kw for kw in keywords_en if kw.lower() in title_lower]
            )
            matched_en_abstract = unique_in_order(
                [kw for kw in keywords_en if kw.lower() in abstract_lower]
            )

        p["_recent"] = is_recent(year, 100)  # Always True effectively
        p["_abstract_usable"] = bool(abstract.strip())
        p["_abstract_issues"] = []
        p["_match_title_zh"] = matched_zh_title
        p["_match_abstract_zh"] = matched_zh_abstract
        p["_match_title_en"] = matched_en_title
        p["_match_abstract_en"] = matched_en_abstract
        p["_link_status"] = "unchecked"
        p["_recovered"] = True  # Mark as recovered
        recovered.append(p)

    recovered.sort(key=lambda paper: (paper.get("year") or 0, paper.get("enhanced_score") or 0), reverse=True)
    return recovered


def citation_by_title(title: str, citations: List[str]) -> Optional[str]:
    for c in citations:
        if title and title in c:
            return c
    return None


def main() -> int:
    args = parse_args()
    input_paths = [Path(p) for p in args.inputs]

    keywords_zh = split_keywords(args.keywords_zh)
    keywords_en = split_keywords(args.keywords_en)
    if args.topic:
        keywords_zh.append(args.topic)
        keywords_en.append(args.topic)

    demand_path = Path(args.demand_file)
    demand_zh, demand_en = collect_keywords_from_file(demand_path)
    input_dir = Path(args.input_dir)
    input_zh, input_en = collect_keywords_from_input_dir(input_dir) if not (demand_zh or demand_en) else ([], [])

    aggregated_zh: List[str] = []
    aggregated_en: List[str] = []

    aggregated_zh.extend(keywords_zh)
    aggregated_en.extend(keywords_en)

    if demand_zh or demand_en:
        aggregated_zh.extend(demand_zh)
        aggregated_en.extend(demand_en)
        source_hint = "客户诉求"
    else:
        aggregated_zh.extend(input_zh)
        aggregated_en.extend(input_en)
        source_hint = "input fallback"

    keywords_zh = dedupe_keywords(aggregated_zh)
    keywords_en = dedupe_keywords(aggregated_en)

    if not keywords_zh and not keywords_en:
        msg = (
            "未从客户诉求或 input 中提取到关键词；请先在 "
            f'{demand_path} 的"关键词"部分或 input 里补充题目/关键词再尝试。'
        )
        print(msg)
        raise SystemExit(1)

    allow_english = args.allow_english or bool(keywords_en)

    print(
        f"关键词来源: {source_hint}; "
        f"demand file: {demand_path if demand_path.exists() else '缺失'}; "
        f"input dir: {input_dir if input_dir.exists() else '缺失'}"
    )
    print(
        f"使用中文关键词 ({len(keywords_zh)}): {keywords_zh}; "
        f"英文关键词 ({len(keywords_en)}): {keywords_en}"
    )

    # Phase 1: Strict filtering
    include_all_related = not args.strict_filter
    selected = select_papers_strict(
        input_paths,
        keywords_zh,
        keywords_en,
        allow_english,
        args.recent_years,
        args.min_abstract_length,
        args.exclude_scholar_snippet,
        args.no_link_check,
        include_all_related,
    )

    print(f"ℹ️ 严格筛选完成：{len(selected)} 篇文献（年份≤{args.recent_years}年，摘要≥{args.min_abstract_length}字）")

    # Phase 2: Recovery if needed
    recovered: List[Dict] = []
    if not args.disable_recovery and len(selected) < args.recovery_threshold:
        print(f"⚠️  文献数量不足（{len(selected)} < {args.recovery_threshold}），启动捡漏机制...")
        print("🔍 捡漏标准：仅检查主题相关性，忽略年份、摘要长度、来源限制")

        already_selected_titles = {p.get("title", "") for p in selected}
        recovered = recover_papers_relaxed(
            input_paths,
            keywords_zh,
            keywords_en,
            allow_english,
            already_selected_titles,
        )

        if recovered:
            print(f"✅ 捡漏成功：从原始结果中找回 {len(recovered)} 篇相关文献")
        else:
            print(f"❌ 捡漏失败：原始结果中无更多相关文献可补充")

    # Combine selected and recovered
    all_papers = selected + recovered

    if len(all_papers) < args.min_count:
        print(f"\n⚠️  最终文献数量：{len(all_papers)} 篇（目标 {args.min_count} 篇）")
        print("💡 建议：")
        print("   1. 检查关键词是否准确，可补充同义词")
        print("   2. 考虑放宽检索条件重新检索")
        print("   3. 手动补充相关文献到文献列表中")

    # Output
    citations = load_citations(input_paths)

    output_lines: List[str] = []
    output_lines.append("# 文献详细列表（筛选版）")
    output_lines.append("")
    output_lines.append("## A. 文献详细信息区")
    output_lines.append("")

    if all_papers:
        output_lines.append("### 中文文献")
        output_lines.append("")

        for idx, p in enumerate(all_papers, 1):
            title = (p.get("title") or "N/A").rstrip("。.")
            authors = ", ".join(p.get("authors") or []) or "N/A"
            year = p.get("year") or "N/A"
            doi = p.get("doi") or "N/A"
            url = p.get("url") or "N/A"
            pdf_url = (
                p.get("pdf_url")
                or p.get("oa_pdf_url")
                or p.get("pdf_source_url")
                or "N/A"
            )
            abstract = p.get("abstract") or p.get("snippet") or ""
            abstract_source = p.get("abstract_source") or "N/A"
            publication_summary = p.get("publication_summary") or "N/A"
            link_status = p.get("_link_status") or "N/A"
            abstract_usable = p.get("_abstract_usable", bool(abstract))
            abstract_issues = p.get("_abstract_issues", [])
            recent_flag = p.get("_recent")
            quality = p.get("abstract_quality", {})
            quality_score = quality.get("score")
            quality_label = quality.get("quality")
            match_title_zh = p.get("_match_title_zh", [])
            match_abstract_zh = p.get("_match_abstract_zh", [])
            match_title_en = p.get("_match_title_en", [])
            match_abstract_en = p.get("_match_abstract_en", [])
            is_recovered = p.get("_recovered", False)

            output_lines.append(f"### {idx}. {title}")
            output_lines.append(f"- **作者**: {authors}")
            output_lines.append(f"- **年份**: {year}")

            if is_recovered:
                output_lines.append(f"- **来源**: ⚠️ 捡漏补充（放宽限制）")
            elif recent_flag is False and year != "N/A":
                output_lines.append(f"- **年份说明**: 非近 {args.recent_years} 年范围")

            relevance_parts: List[str] = []
            if match_title_zh or match_title_en:
                title_hits: List[str] = []
                if match_title_zh:
                    title_hits.append(f"中文: {', '.join(match_title_zh)}")
                if match_title_en:
                    title_hits.append(f"英文: {', '.join(match_title_en)}")
                relevance_parts.append(f"标题命中({'; '.join(title_hits)})")
            if match_abstract_zh or match_abstract_en:
                abstract_hits: List[str] = []
                if match_abstract_zh:
                    abstract_hits.append(f"中文: {', '.join(match_abstract_zh)}")
                if match_abstract_en:
                    abstract_hits.append(f"英文: {', '.join(match_abstract_en)}")
                relevance_parts.append(f"摘要命中({'; '.join(abstract_hits)})")
            if relevance_parts:
                output_lines.append(f"- **相关性**: {'; '.join(relevance_parts)}")

            output_lines.append(f"- **出版信息**: {publication_summary}")
            output_lines.append(f"- **DOI**: {doi}")
            output_lines.append(f"- **链接**: {url}")
            if pdf_url != "N/A":
                output_lines.append(f"- **PDF**: {pdf_url}")
            if link_status != "unchecked":
                output_lines.append(
                    f"- **链接验证状态**: {link_status if link_status == 'N/A' else 'HTTP ' + link_status}"
                )
            output_lines.append(f"- **摘要来源**: {abstract_source}")

            if quality_score:
                quality_text = (
                    f"{quality_score}/100"
                    + (f" ({quality_label})" if quality_label else "")
                )
                output_lines.append(f"- **摘要质量**: {quality_text}")

            abstract_notes: List[str] = []
            if abstract_source == "scholar_snippet":
                abstract_notes.append("Scholar 片段")
            if abstract_issues:
                abstract_notes.extend(abstract_issues)
            if abstract_notes:
                output_lines.append(f"- **摘要说明**: {' / '.join(abstract_notes)}")

            if abstract_usable:
                output_lines.append(
                    f"- **摘要**: {clean_abstract(abstract, args.max_abstract_length)}"
                )
            else:
                output_lines.append("- **摘要**: N/A")
            output_lines.append("")
    else:
        output_lines.append("- 暂无符合条件的文献")
        output_lines.append("")

    output_lines.append("## B. GB/T7714-2015 引用列表区")
    output_lines.append("")

    citation_lines: List[str] = []
    for idx, p in enumerate(all_papers, 1):
        title = p.get("title") or ""
        c = citation_by_title(title, citations)
        if not c:
            authors = ", ".join(p.get("authors") or []) or "N/A"
            year = p.get("year") or "N/A"
            url = p.get("url") or p.get("pdf_url") or "N/A"
            c = f"[{idx}] {authors}. {title}[J/OL]. {year}. {url}"
        c = re.sub(r"^\[\d+\]", f"[{idx}]", c)
        citation_lines.append(c)

    if citation_lines:
        output_lines.extend(citation_lines)
    else:
        output_lines.append("- 暂无")

    output_lines.append("")
    output_lines.append("## 数量校验")
    if recovered:
        output_lines.append(f"- 严格筛选: {len(selected)} 篇")
        output_lines.append(f"- 捡漏补充: {len(recovered)} 篇")
    output_lines.append(
        f"- **总计**: {len(all_papers)} 篇（目标数量：{args.min_count}）"
    )

    if len(all_papers) < args.min_count:
        output_lines.append("")
        output_lines.append("## ⚠️ 文献数量不足")
        output_lines.append("")
        output_lines.append("**情况说明**：")
        output_lines.append(f"- 原始检索结果总数: {len(load_papers(input_paths))} 篇")
        output_lines.append(f"- 严格筛选（近{args.recent_years}年，摘要≥{args.min_abstract_length}字）: {len(selected)} 篇")
        if recovered:
            output_lines.append(f"- 捡漏补充（仅相关性）: {len(recovered)} 篇")
        output_lines.append("")
        output_lines.append("**可能原因**：")
        output_lines.append("1. 检索关键词与主题匹配度不足")
        output_lines.append("2. 该领域文献数量较少")
        output_lines.append("3. 检索时间范围或数据库覆盖有限")
        output_lines.append("")
        output_lines.append("**建议**：")
        output_lines.append("1. 补充同义词、缩写、相关术语作为关键词")
        output_lines.append("2. 手动检索并补充相关文献")
        output_lines.append("3. 考虑扩大检索范围或更换数据库")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines), encoding="utf-8")

    print(f"✅ 输出完成: {output_path}")
    print(f"📊 最终文献数量: {len(all_papers)} 篇（严格筛选 {len(selected)} 篇 + 捡漏 {len(recovered)} 篇）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
