#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键：扫描正文占位符 → 生成规格清单 → 按规格生成图表。
所有路径通过参数传入，不依赖固定命名。
"""
import sys
import argparse
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="正文 + 案例与数据文档 → 图表资源目录")
    parser.add_argument("--thesis-md", required=True, help="正文 Markdown 路径")
    parser.add_argument("--data-doc", default=None, help="案例与数据文档路径（可选）")
    parser.add_argument("--output-dir", default="output/work/正文插图与表格", help="图表输出目录")
    parser.add_argument("--data-root", default=".", help="项目根目录，用于 data_path")
    parser.add_argument("--spec-output", default=None, help="figures_spec 输出路径；不指定则用 output/work/figures_spec.yaml")
    args = parser.parse_args()

    thesis_md = Path(args.thesis_md)
    if not thesis_md.exists():
        print(f"错误：正文不存在 {thesis_md}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    data_root = Path(args.data_root).resolve()
    spec_output = Path(args.spec_output or "output/work/figures_spec.yaml")

    # 1) 扫描占位符
    placeholders_json = output_dir.parent / "placeholders.json"
    placeholders_json.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scan_placeholders.py"),
         "--thesis-md", str(thesis_md),
         "--output-json", str(placeholders_json)],
        cwd=data_root,
    )
    if r.returncode != 0:
        sys.exit(r.returncode)

    # 2) 生成规格
    cmd_build = [sys.executable, str(SKILL_DIR / "build_spec_from_doc.py"),
                 "--thesis-md", str(thesis_md),
                 "--spec-output", str(spec_output),
                 "--output-dir", str(output_dir),
                 "--data-root", str(data_root)]
    if args.data_doc and Path(args.data_doc).exists():
        cmd_build.extend(["--data-doc", str(args.data_doc)])
    cmd_build.extend(["--placeholders-json", str(placeholders_json)])
    r = subprocess.run(cmd_build, cwd=data_root)
    if r.returncode != 0:
        sys.exit(r.returncode)

    # 3) 按规格生成
    r = subprocess.run(
        [sys.executable, str(SKILL_DIR / "generate_from_spec.py"),
         "--spec", str(spec_output),
         "--output-dir", str(output_dir),
         "--data-root", str(data_root)],
        cwd=data_root,
    )
    sys.exit(r.returncode if r.returncode is not None else 0)


if __name__ == "__main__":
    main()
