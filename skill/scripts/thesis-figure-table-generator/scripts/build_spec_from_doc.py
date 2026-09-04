#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
占位符 + 案例/数据文档 → figures_spec.yaml。
核心能力：自动从 Markdown 文件中提取匹配标题的表格数据，并将 Excel/CSV 路径映射到数据源。
"""
import re
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

def extract_markdown_table(doc_path: Path, title: str) -> Optional[Dict[str, Any]]:
    """从 Markdown 文档中提取特定标题下的表格数据"""
    if not doc_path.exists(): return None
    text = doc_path.read_text(encoding="utf-8")
    
    # 清理标题以提高匹配率
    clean_title = re.sub(r"^[图表]\d+[-.]\d+\s*[:：]\s*", "", title).strip()
    
    # 查找包含该标题的标题行 (支持不同层级 #)
    header_pattern = re.compile(rf"#{1,6}\s+.*{re.escape(clean_title)}.*")
    m = header_pattern.search(text)
    if not m: return None

    # 提取标题后的第一个表格
    after_text = text[m.end():]
    # 表格正则：匹配 | 单元格 | 结构
    table_pattern = re.compile(r"\|.*\|\n\|[- :|]+\|\n((?:\|.*\|\n?)+)")
    tm = table_pattern.search(after_text)
    if not tm: return None

    lines = tm.group(0).strip().split("\n")
    headers = [c.strip() for c in lines[0].split("|") if c.strip()]
    rows = []
    for r in lines[2:]:
        rows.append([c.strip() for c in r.split("|") if c.strip()])
    return {"headers": headers, "rows": rows}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--thesis-md", required=True)
    parser.add_argument("--data-doc", default=None)
    parser.add_argument("--placeholders-json", default=None)
    parser.add_argument("--spec-output", required=True)
    parser.add_argument("--output-dir", default="output/deliver/论文图表")
    parser.add_argument("--data-root", default=".")
    args = parser.parse_args()

    # 加载占位符
    if args.placeholders_json and Path(args.placeholders_json).exists():
        p_data = json.loads(Path(args.placeholders_json).read_text(encoding="utf-8"))
        placeholders = p_data.get("placeholders", [])
    else:
        from scan_placeholders import scan_markdown
        placeholders = scan_markdown(Path(args.thesis_md))

    data_doc_path = Path(args.data_doc) if args.data_doc else None
    
    items = []
    for p in placeholders:
        spec = {
            "id": p["id"],
            "title": p["title"],
            "type": p["type"],
            "data_source": (p.get("data_source") or "").strip()
        }
        
        ds = spec["data_source"]
        # 1. 自动处理显式的文件路径
        if ds and (ds.lower().endswith((".xlsx", ".csv"))):
            spec["data_path"] = ds
        
        # 2. 如果是表格且数据源指向文档，尝试从文档提取
        if spec["type"] == "table" and data_doc_path:
            # 如果没指定 data_path 或 data_path 就是 data_doc 本身
            if not spec.get("data_path") or spec["data_path"] == str(data_doc_path):
                table_data = extract_markdown_table(data_doc_path, spec["title"])
                if table_data:
                    spec["options"] = table_data
                    spec["data_path"] = None # 标记不再从文件读取
        
        # 3. 截图类处理
        if "截图" in spec["title"] or "界面" in spec["title"]:
            spec["type"] = "screenshot_placeholder"
            spec["manual"] = True

        items.append(spec)

    out = {
        "output_dir": args.output_dir,
        "data_root": args.data_root,
        "items": items
    }
    
    out_path = Path(args.spec_output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if yaml:
        out_path.write_text(yaml.dump(out, allow_unicode=True, sort_keys=False), encoding="utf-8")
    else:
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated spec with {len(items)} items -> {out_path}")

if __name__ == "__main__":
    main()
