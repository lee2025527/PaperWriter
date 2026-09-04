#!/usr/bin/env python3
"""
OpenAlex abstract enrichment tool.
Reads SerpAPI output JSON and replaces snippet abstracts with reconstructed
OpenAlex abstracts when available. Writes new JSON/MD files.
"""

import argparse
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def extract_doi(*values: str) -> str:
    for value in values:
        if not value:
            continue
        match = DOI_REGEX.search(value)
        if match:
            doi = match.group(0).strip().rstrip(").,;]>} ")
            return doi
    return ""


def reconstruct_abstract(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    if not inverted_index:
        return ""
    positions: List[int] = []
    for indices in inverted_index.values():
        positions.extend(indices)
    if not positions:
        return ""
    max_index = max(positions)
    words: List[Optional[str]] = [None] * (max_index + 1)
    for word, indices in inverted_index.items():
        for index in indices:
            if 0 <= index < len(words):
                words[index] = word
    return " ".join(word for word in words if word)


def openalex_request(url: str, ca_bundle: str) -> Optional[Dict[str, Any]]:
    context = None
    if ca_bundle:
        context = ssl.create_default_context(cafile=ca_bundle)
    try:
        with urllib.request.urlopen(url, timeout=30, context=context) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        print(f"   ⚠️ OpenAlex HTTP 错误: {exc.code}")
        return None
    except urllib.error.URLError as exc:
        print(f"   ⚠️ OpenAlex 连接失败: {exc.reason}")
        return None


def build_select_params() -> str:
    fields = [
        "abstract_inverted_index",
        "doi",
        "display_name",
        "publication_year",
        "best_oa_location",
        "ids",
    ]
    return ",".join(fields)


def fetch_by_doi(doi: str, email: str, ca_bundle: str) -> Optional[Dict[str, Any]]:
    encoded = urllib.parse.quote(f"https://doi.org/{doi}", safe="")
    url = f"https://api.openalex.org/works/{encoded}?select={build_select_params()}"
    if email:
        url += f"&mailto={urllib.parse.quote(email)}"
    return openalex_request(url, ca_bundle)


def fetch_by_title(title: str, email: str, ca_bundle: str) -> Optional[Dict[str, Any]]:
    if not title:
        return None
    query = urllib.parse.quote(title)
    url = f"https://api.openalex.org/works?search={query}&per-page=1&select={build_select_params()}"
    if email:
        url += f"&mailto={urllib.parse.quote(email)}"
    data = openalex_request(url, ca_bundle)
    if not data:
        return None
    results = data.get("results") or []
    return results[0] if results else None


def enrich_paper(paper: Dict[str, Any], email: str, ca_bundle: str, sleep_s: float) -> Dict[str, Any]:
    paper.setdefault("snippet", paper.get("abstract", ""))
    doi = paper.get("doi") or extract_doi(
        paper.get("url", ""),
        paper.get("publication_summary", ""),
        paper.get("abstract", ""),
    )

    match_type = ""
    data = None
    if doi:
        data = fetch_by_doi(doi, email, ca_bundle)
        match_type = "doi" if data else ""

    if not data:
        data = fetch_by_title(paper.get("title", ""), email, ca_bundle)
        match_type = "title" if data else ""

    if sleep_s:
        time.sleep(sleep_s)

    if not data:
        paper["abstract_source"] = "scholar_snippet"
        return paper

    inverted = data.get("abstract_inverted_index")
    full_abstract = reconstruct_abstract(inverted)
    if full_abstract:
        paper["abstract"] = full_abstract
        paper["abstract_source"] = "openalex"
    else:
        paper["abstract_source"] = "scholar_snippet"

    paper["doi"] = data.get("doi") or doi
    ids = data.get("ids") or {}
    paper["openalex_id"] = ids.get("openalex") or data.get("id")
    paper["openalex_match"] = match_type or "unknown"
    best_oa = data.get("best_oa_location") or {}
    paper["oa_pdf_url"] = best_oa.get("pdf_url") or ""

    return paper


def write_markdown(output_path: str, result: Dict[str, Any], stats: Dict[str, Any]) -> None:
    papers = result.get("search_results", {}).get("papers", [])
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# OpenAlex 摘要增强报告\n\n")
        f.write("## 增强统计\n")
        f.write(f"- **总文献数**: {stats['total']}\n")
        f.write(f"- **摘要更新数**: {stats['abstract_updated']}\n")
        f.write(f"- **OpenAlex 命中(doi)**: {stats['matched_doi']}\n")
        f.write(f"- **OpenAlex 命中(title)**: {stats['matched_title']}\n\n")

        f.write("## 文献列表\n\n")
        for i, paper in enumerate(papers, 1):
            f.write(f"### {i}. {paper.get('title', 'N/A')}\n")
            f.write(f"- **作者**: {', '.join(paper.get('authors', [])) or '佚名'}\n")
            f.write(f"- **年份**: {paper.get('year') or 'N.D.'}\n")
            f.write(f"- **DOI**: {paper.get('doi') or 'N/A'}\n")
            f.write(f"- **OpenAlex ID**: {paper.get('openalex_id') or 'N/A'}\n")
            f.write(f"- **摘要来源**: {paper.get('abstract_source')}\n")
            f.write(f"- **链接**: {paper.get('url') or 'N/A'}\n")
            if paper.get("oa_pdf_url"):
                f.write(f"- **PDF**: {paper.get('oa_pdf_url')}\n")
            if paper.get("publication_summary"):
                f.write(f"- **出版信息**: {paper.get('publication_summary')}\n")
            if paper.get("abstract"):
                f.write(f"- **摘要**: {paper.get('abstract')}\n")
            f.write("\n")


def process_file(path: str, output_dir: str, email: str, ca_bundle: str, sleep_s: float) -> None:
    with open(path, "r", encoding="utf-8") as f:
        result = json.load(f)

    papers = result.get("search_results", {}).get("papers") or []
    base_name = os.path.splitext(os.path.basename(path))[0]
    output_json = os.path.join(output_dir, f"{base_name}_openalex.json")
    output_md = os.path.join(output_dir, f"{base_name}_openalex.md")

    if not papers:
        print(f"❌ 未找到文献列表: {path}")
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        with open(output_md, "w", encoding="utf-8") as f:
            f.write("# OpenAlex 摘要增强报告\n\n")
            f.write("## 提示\n")
            f.write(f"- 原始文件 {os.path.basename(path)} 中未包含任何文献，故未进行增强。\n")
        return

    print(f"🔍 处理文件: {os.path.basename(path)}")
    matched_doi = 0
    matched_title = 0
    abstract_updated = 0

    for paper in papers:
        before = paper.get("abstract", "")
        enriched = enrich_paper(paper, email, ca_bundle, sleep_s)
        if enriched.get("openalex_match") == "doi":
            matched_doi += 1
        elif enriched.get("openalex_match") == "title":
            matched_title += 1
        if enriched.get("abstract_source") == "openalex" and enriched.get("abstract") != before:
            abstract_updated += 1

    stats = {
        "total": len(papers),
        "matched_doi": matched_doi,
        "matched_title": matched_title,
        "abstract_updated": abstract_updated,
    }
    result["openalex_enrichment"] = {
        "mailto": email,
        "ca_bundle": bool(ca_bundle),
        "stats": stats,
    }

    base_name = os.path.splitext(os.path.basename(path))[0]
    output_json = os.path.join(output_dir, f"{base_name}_openalex.json")
    output_md = os.path.join(output_dir, f"{base_name}_openalex.md")

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    write_markdown(output_md, result, stats)

    print(f"✅ 输出完成: {output_json}")
    print(f"✅ 输出完成: {output_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAlex 摘要增强工具")
    parser.add_argument("inputs", nargs="+", help="SerpAPI 输出 JSON 文件路径")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    parser.add_argument("--email", default=os.getenv("OPENALEX_EMAIL", ""), help="OpenAlex mailto 参数")
    parser.add_argument("--sleep", type=float, default=0.1, help="每次请求后的休眠秒数")
    args = parser.parse_args()

    ca_bundle = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or ""

    for input_path in args.inputs:
        process_file(input_path, args.output_dir, args.email, ca_bundle, args.sleep)


if __name__ == "__main__":
    main()
