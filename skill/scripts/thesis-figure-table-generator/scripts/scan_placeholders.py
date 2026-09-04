#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用占位符扫描器：从 Markdown 中提取图表占位符。
支持格式：
  - > [插入图1-1：系统架构图 | 类型: 架构图 | 数据来源: path/to/data.xlsx]
  - > [图2-3：性能对比 | 类型: 柱状图]
  - **表 3-1  测试用例汇总**
"""
import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

# 灵活的图占位符正则：支持 插入、图/Fig/Figure、冒号中英文、可选类型和数据源
FIGURE_PATTERN = re.compile(
    r'>\s*\[(?:插入)?(?:图|Fig|Figure)\s*(\d+)[-.](\d+)\s*[:：]\s*([^\]|]+)'
    r'(?:\s*\|\s*类型:\s*([^|]+))?'
    r'(?:\s*\|\s*数据来源:\s*([^\]]+))?\s*\]', re.I
)

# 灵活的表占位符正则
TABLE_MARKDOWN_PATTERN = re.compile(
    r'>\s*\[(?:插入)?(?:表|Table)\s*(\d+)[-.](\d+)\s*[:：]\s*([^\]|]+)'
    r'(?:\s*\|\s*类型:\s*([^|]+))?'
    r'(?:\s*\|\s*数据来源:\s*([^\]]+))?\s*\]', re.I
)

# 传统的加粗表题格式
TABLE_BOLD_PATTERN = re.compile(
    r'\*\*(?:表|Table)\s*(\d+)[-.](\d+)\s+([^*]+)\*\*', re.I
)

TYPE_MAP = {
    "架构图": "architecture",
    "架构": "architecture",
    "流程图": "flowchart",
    "流程": "flowchart",
    "折线图": "line_chart",
    "折线": "line_chart",
    "趋势图": "line_chart",
    "趋势": "line_chart",
    "柱状图": "bar_chart",
    "柱状": "bar_chart",
    "对比": "bar_chart",
    "饼图": "pie_chart",
    "占比": "pie_chart",
    "分布": "pie_chart",
    "表格": "table",
    "截图": "screenshot_placeholder",
    "界面": "screenshot_placeholder",
    "混淆矩阵": "confusion_matrix",
}

def scan_markdown(md_path: Path) -> List[Dict[str, Any]]:
    items = []
    if not md_path.exists(): return items
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    for line_no, line in enumerate(lines, 1):
        line = line.strip()
        # 1. 匹配图
        m = FIGURE_PATTERN.search(line)
        if m:
            ch, sec, title = m.group(1), m.group(2), m.group(3).strip()
            raw_type = (m.group(4) or "").strip()
            data_src = (m.group(5) or "").strip()
            items.append({
                "id": f"图{ch}-{sec}",
                "kind": "figure",
                "title": title,
                "type": TYPE_MAP.get(raw_type, "flowchart" if "流程" in title else "bar_chart"),
                "data_source": data_src,
                "line_number": line_no,
                "original": m.group(0)
            })
            continue

        # 2. 匹配表 (Markdown 格式)
        m = TABLE_MARKDOWN_PATTERN.search(line)
        if m:
            ch, sec, title = m.group(1), m.group(2), m.group(3).strip()
            data_src = (m.group(5) or "").strip()
            items.append({
                "id": f"表{ch}-{sec}",
                "kind": "table",
                "title": title,
                "type": "table",
                "data_source": data_src,
                "line_number": line_no,
                "original": m.group(0)
            })
            continue

        # 3. 匹配表 (加粗格式)
        m = TABLE_BOLD_PATTERN.search(line)
        if m:
            ch, sec, title = m.group(1), m.group(2), m.group(3).strip()
            items.append({
                "id": f"表{ch}-{sec}",
                "kind": "table",
                "title": title,
                "type": "table",
                "data_source": "",
                "line_number": line_no,
                "original": m.group(0)
            })

    return items

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--thesis-md", required=True)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()
    
    res = scan_markdown(Path(args.thesis_md))
    out = {"count": len(res), "placeholders": res}
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
