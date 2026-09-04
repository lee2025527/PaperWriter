#!/usr/bin/env python3
"""
Run the full literature pipeline:
1) SerpAPI search (zh/en)
2) OpenAlex abstract enrichment
3) Stage3 fallback enrichment
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def normalize_keywords(text: str) -> str:
    if not text:
        return ""
    cleaned = (
        text.replace("，", ",")
        .replace(";", ",")
        .replace("\n", ",")
        .replace("\r", ",")
    )
    tokens = [item.strip() for item in cleaned.split(",") if item.strip()]
    return ",".join(tokens)


def read_keywords_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return normalize_keywords(content)


def build_prefix(topic: str, output: str, output_dir: Path) -> str:
    if output:
        base = Path(output).name or Path(output).stem or output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"literature_pipeline_{timestamp}"
    return str(output_dir / base)


def run_step(cmd, env, cwd, label):
    print(f"▶ {label}")
    result = subprocess.run(cmd, env=env, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")


def ensure_stub_json(path: str) -> None:
    if os.path.exists(path):
        return
    stub = {"search_results": {"papers": []}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stub, f, ensure_ascii=False, indent=2)


def load_paper_count(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return 0
    return len(data.get("search_results", {}).get("papers", []))


def parse_english_requirement(requirements_path: str) -> tuple[bool, int]:
    if not os.path.exists(requirements_path):
        return False, 0
    text = Path(requirements_path).read_text(encoding="utf-8")
    negative = re.search(
        r"(?:无需|不用|不需要|不强求|可不|无须|未要求).{0,6}英文",
        text,
        flags=re.IGNORECASE,
    )
    if negative:
        return False, 0

    count_match = re.search(
        r"(?:英文文献|英文论文|English papers?|English literature).{0,20}?(\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if count_match and count_match.group(1):
        return True, max(1, int(count_match.group(1)))

    positive = re.search(
        r"(?:必须|需|需要|至少|应|须).{0,12}?(?:英文文献|英文论文|English)",
        text,
        flags=re.IGNORECASE,
    )
    if positive:
        return True, 1

    return False, 0


def main() -> None:
    parser = argparse.ArgumentParser(description="One-shot literature pipeline")
    parser.add_argument("topic", nargs="?", help="论文题目")
    parser.add_argument("keywords_zh", nargs="?", help="中文关键词（逗号分隔）")
    parser.add_argument("keywords_en", nargs="?", help="英文关键词（逗号分隔）")
    parser.add_argument("major", nargs="?", default="", help="专业领域")
    parser.add_argument("direction", nargs="?", default="", help="研究方向")
    parser.add_argument("max_results", nargs="?", type=int, default=0, help="最大结果数 (0=不限制, 默认单次调用)")

    parser.add_argument("--topic", dest="topic_opt", help="论文题目")
    parser.add_argument("--keywords-zh", dest="keywords_zh_opt", help="中文关键词（逗号分隔）")
    parser.add_argument("--keywords-en", dest="keywords_en_opt", help="英文关键词（逗号分隔）")
    parser.add_argument("--keywords-zh-file", help="中文关键词文件路径")
    parser.add_argument("--keywords-en-file", help="英文关键词文件路径")
    parser.add_argument("--major", dest="major_opt", default="", help="专业领域")
    parser.add_argument("--direction", dest="direction_opt", default="", help="研究方向")
    parser.add_argument("--max", type=int, default=18, dest="max_results_opt", help="最大结果数")
    parser.add_argument("--output", help="输出文件名前缀")
    parser.add_argument("--serpapi-key", dest="serpapi_key", help="SerpAPI API Key")
    parser.add_argument("--ca-bundle", dest="ca_bundle", default="", help="CA 证书文件路径")
    parser.add_argument("--email", default=os.getenv("OPENALEX_EMAIL", ""), help="OpenAlex mailto 参数(可用环境变量 OPENALEX_EMAIL)")
    parser.add_argument("--stage3-min-length", type=int, default=120, help="第三步摘要最小长度")
    parser.add_argument("--stage3-max-requests", type=int, default=120, help="第三步最大请求次数")
    parser.add_argument("--stage3-max-seconds", type=int, default=120, help="第三步最大耗时秒数")
    parser.add_argument("--stage3-sleep", type=float, default=0.1, help="第三步请求间隔")
    parser.add_argument("--stage3-timeout", type=int, default=20, help="第三步单次请求超时")
    parser.add_argument("--stage3-max-pdf-chars", type=int, default=2000, help="第三步PDF摘要字符数上限")
    parser.add_argument("--stage3-no-crossref", action="store_true", help="第三步关闭 Crossref")
    parser.add_argument("--stage3-no-unpaywall", action="store_true", help="第三步关闭 Unpaywall")
    parser.add_argument("--stage3-no-html", action="store_true", help="第三步关闭 HTML Meta")
    parser.add_argument("--stage3-no-pdf", action="store_true", help="第三步关闭 PDF 抽取")

    # V5 新增参数
    parser.add_argument("--min-score", type=int, default=60, dest="min_quality_score",
                        help="最低质量分数 (0-100, 默认: 60)")
    parser.add_argument("--max-rounds", type=int, default=3, help="目标模式最大搜索轮数 (默认: 3)")
    parser.add_argument("--no-target-rounds", type=int, default=1, help="无目标模式默认轮数 (默认: 1)")
    parser.add_argument("--no-related", action="store_true", help="关闭相关搜索功能")
    parser.add_argument("--num-per-call", type=int, default=20, help="每次API调用最大请求数 (默认: 20)")
    parser.add_argument(
        "--keep-all-results",
        action="store_true",
        help="保留API返回的全部结果（等同于 min-score=0）",
    )

    args = parser.parse_args()

    if args.keep_all_results:
        args.min_quality_score = 0

    topic = args.topic_opt or args.topic or ""
    if not topic:
        raise SystemExit("❌ 错误: 缺少论文题目")

    keywords_zh = ""
    if args.keywords_zh_file:
        keywords_zh = read_keywords_file(args.keywords_zh_file)
    else:
        keywords_zh = args.keywords_zh_opt or args.keywords_zh or ""

    keywords_en = ""
    if args.keywords_en_file:
        keywords_en = read_keywords_file(args.keywords_en_file)
    else:
        keywords_en = args.keywords_en_opt or args.keywords_en or ""

    keywords_zh = normalize_keywords(keywords_zh)
    keywords_en = normalize_keywords(keywords_en)

    if not keywords_zh or not keywords_en:
        raise SystemExit("❌ 错误: 请同时提供中英文关键词（或对应文件）")

    major = args.major_opt or args.major or ""
    direction = args.direction_opt or args.direction or ""
    max_results = args.max_results_opt or args.max_results or 18

    serpapi_key = args.serpapi_key or os.getenv("SERPAPI_KEY") or os.getenv("SERPAPI_API_KEY")
    if not serpapi_key:
        raise SystemExit("❌ 错误: 缺少 SerpAPI KEY")

    ca_bundle = args.ca_bundle or os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or ""

    intermediate_dir = Path("output") / "work" / "文献检索中间产物"
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    prefix = build_prefix(topic, args.output or "", intermediate_dir)
    zh_output = f"{prefix}_zh"
    en_output = f"{prefix}_en"

    env = os.environ.copy()
    env["SERPAPI_KEY"] = serpapi_key
    if ca_bundle:
        env["SSL_CERT_FILE"] = ca_bundle

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()

    step1 = os.path.join(script_dir, "literature_search_optimized_v5.py")
    step2 = os.path.join(script_dir, "enrich_abstracts.py")
    step3 = os.path.join(script_dir, "enrich_abstracts_stage3.py")

    run_step(
        [
            sys.executable,
            step1,
            topic,
            keywords_zh,
            major,
            direction,
            str(max_results),
            "--output",
            zh_output,
            "--min-score", str(args.min_quality_score),
            "--max-rounds", str(args.max_rounds),
            "--no-target-rounds", str(args.no_target_rounds),
            "--num-per-call", str(args.num_per_call),
        ] + (["--no-related"] if args.no_related else []),
        env,
        cwd,
        "Step1 (ZH) SerpAPI search (V5)",
    )
    zh_json = f"{zh_output}.json"
    zh_count = load_paper_count(zh_json)

    requirements_path = os.path.join("output", "work", "客户诉求.md")
    english_required, english_target = parse_english_requirement(requirements_path)
    skip_en = zh_count >= max_results and not english_required
    if skip_en:
        print(f"ℹ️ 中文文献检索已达到 {zh_count} 篇，跳过英文轨道")
        ensure_stub_json(f"{en_output}.json")
    else:
        run_step(
            [
                sys.executable,
                step1,
                topic,
                keywords_en,
                major,
                direction,
                str(max_results),
                "--output",
                en_output,
                "--min-score", str(args.min_quality_score),
                "--max-rounds", str(args.max_rounds),
                "--no-target-rounds", str(args.no_target_rounds),
                "--num-per-call", str(args.num_per_call),
            ] + (["--no-related"] if args.no_related else []),
            env,
            cwd,
            "Step1 (EN) SerpAPI search (V5)",
        )
        en_count = load_paper_count(f"{en_output}.json")
        if english_required and en_count < english_target:
            print(
                f"⚠️ 英文文献要求 {english_target} 篇，当前仅检索到 {en_count} 篇，可能需要补充关键词或手动扩展。"
            )

    run_step(
        [
            sys.executable,
            step2,
            f"{zh_output}.json",
            f"{en_output}.json",
            "--email",
            args.email,
            "--output-dir",
            str(intermediate_dir),
        ],
        env,
        cwd,
        "Step2 OpenAlex enrichment",
    )

    stage3_cmd = [
        sys.executable,
        step3,
        f"{zh_output}_openalex.json",
        f"{en_output}_openalex.json",
        "--email",
        args.email,
        "--min-length",
        str(args.stage3_min_length),
        "--max-requests",
        str(args.stage3_max_requests),
        "--max-seconds",
        str(args.stage3_max_seconds),
        "--sleep",
        str(args.stage3_sleep),
        "--timeout",
        str(args.stage3_timeout),
        "--max-pdf-chars",
        str(args.stage3_max_pdf_chars),
        "--output-dir",
        str(intermediate_dir),
    ]
    if args.stage3_no_crossref:
        stage3_cmd.append("--no-crossref")
    if args.stage3_no_unpaywall:
        stage3_cmd.append("--no-unpaywall")
    if args.stage3_no_html:
        stage3_cmd.append("--no-html")
    if args.stage3_no_pdf:
        stage3_cmd.append("--no-pdf")

    run_step(stage3_cmd, env, cwd, "Step3 Stage3 enrichment")

    print("✅ Pipeline complete.")


if __name__ == "__main__":
    main()
