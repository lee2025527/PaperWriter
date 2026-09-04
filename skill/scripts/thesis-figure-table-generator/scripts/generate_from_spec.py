#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 figures_spec.yaml 按类型分发到各生成器，输出图表资源目录与清单。
"""
import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List

# 同目录 generators 包
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import yaml
except ImportError:
    yaml = None

from generators import REGISTRY


def load_spec(spec_path: Path) -> Dict[str, Any]:
    text = spec_path.read_text(encoding="utf-8")
    if spec_path.suffix.lower() in (".yaml", ".yml") and yaml:
        return yaml.safe_load(text)
    return json.loads(text)


def safe_filename(title: str) -> str:
    return "".join(c for c in title if c.isalnum() or c in " _-—（）/")


def main():
    parser = argparse.ArgumentParser(description="按 figures_spec 生成图表并写清单")
    parser.add_argument("--spec", required=True, help="figures_spec.yaml 或 .json 路径")
    parser.add_argument("--output-dir", default=None, help="图表输出目录；不指定则用 spec 内 output_dir")
    parser.add_argument("--data-root", default=None, help="项目根目录，用于解析 data_path；不指定则用 spec 内 data_root")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        raise SystemExit(f"规格文件不存在: {spec_path}")

    spec = load_spec(spec_path)
    output_dir = Path(args.output_dir or spec.get("output_dir", "output/work/正文插图与表格"))
    data_root = Path(args.data_root or spec.get("data_root", "."))
    items = spec.get("items", [])

    output_dir = output_dir.resolve()
    if not data_root.is_absolute():
        data_root = (spec_path.parent / data_root).resolve()
    else:
        data_root = Path(data_root).resolve()

    generated: List[Dict[str, Any]] = []
    for item in items:
        tid = item.get("type", "")
        if item.get("manual") and tid != "screenshot_placeholder":
            tid = "screenshot_placeholder"
        gen = REGISTRY.get(tid)
        if not gen:
            print(f"跳过未知类型: {item.get('id')} type={tid}")
            generated.append({"id": item.get("id"), "title": item.get("title"), "path": None, "manual": True, "reason": f"未知类型 {tid}"})
            continue
        try:
            out_path = gen(item, output_dir, data_root)
            if out_path:
                generated.append({
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "path": str(out_path),
                    "manual": item.get("manual", False),
                })
                print(f"已生成: {out_path}")
        except Exception as e:
            print(f"生成失败 {item.get('id')}: {e}")
            generated.append({"id": item.get("id"), "title": item.get("title"), "path": None, "error": str(e)})

    # 图表清单 README
    readme_lines = [
        "# 图表产出清单",
        "",
        "本目录由 thesis-figure-table-generator 根据 figures_spec 生成。",
        "",
        "| 编号 | 标题 | 文件名/说明 | 状态 |",
        "|------|------|-------------|------|",
    ]
    for g in generated:
        pid = g.get("id", "")
        title = g.get("title", "")
        path = g.get("path")
        manual = g.get("manual", False)
        if path:
            fname = Path(path).name
            status = "需手动截图" if manual else "已生成"
        else:
            fname = g.get("reason", "—")
            status = "未生成"
        readme_lines.append(f"| {pid} | {title} | {fname} | {status} |")
    readme_path = output_dir / "README.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("\n".join(readme_lines), encoding="utf-8")
    print(f"已写入清单: {readme_path}")

    # 可选 manifest JSON
    manifest_path = output_dir / "figures_manifest.json"
    manifest_path.write_text(json.dumps({"generated": generated}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
