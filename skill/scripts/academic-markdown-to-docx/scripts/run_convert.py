#!/usr/bin/env python3
"""
统一入口：将学术论文 Markdown 转为 Word，使用技能内置默认配置或用户指定配置/模板。
跨项目复用时可通过 --tool-dir 指定 universal_md_to_docx.py 所在目录。
"""

import argparse
import os
import subprocess
import sys


def resolve_skill_dir():
    """技能目录：run_convert.py 所在目录的上一级（academic-markdown-to-docx）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_config_path():
    """技能内置默认配置路径。"""
    return os.path.join(resolve_skill_dir(), "config", "default_academic_cn.json")


def default_tool_path():
    """
    本仓库内默认工具路径（相对技能目录：academic-markdown-to-docx -> skills -> 仓库根 -> tools/...）。
    """
    skill_dir = resolve_skill_dir()
    # skill_dir = .../skills/academic-markdown-to-docx
    repo_root = os.path.dirname(os.path.dirname(skill_dir))
    return os.path.join(repo_root, "tools", "文档格式转换工具", "universal_md_to_docx.py")


def main():
    parser = argparse.ArgumentParser(
        description="学术 Markdown 转 Word：使用默认或指定配置/模板，调用 universal_md_to_docx 生成 DOCX。"
    )
    parser.add_argument("--input", required=True, help="输入 Markdown 文件路径")
    parser.add_argument("--output", required=True, help="输出 Word 文件路径")
    parser.add_argument("--template", default=None, help="可选：Word 模板 .docx 路径")
    parser.add_argument(
        "--config",
        default=None,
        help="可选：样式配置 JSON 路径；不传则使用技能内置 default_academic_cn.json",
    )
    parser.add_argument(
        "--tool-dir",
        default=None,
        help="可选：universal_md_to_docx.py 所在目录（跨项目复用时指定）",
    )
    args = parser.parse_args()

    config_path = args.config or default_config_path()
    if not os.path.exists(config_path):
        print(f"Error: Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    if args.tool_dir:
        tool_path = os.path.join(
            os.path.abspath(args.tool_dir), "universal_md_to_docx.py"
        )
    else:
        tool_path = default_tool_path()

    if not os.path.exists(tool_path):
        print(
            f"Error: Converter not found: {tool_path}. Use --tool-dir to specify.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, tool_path, args.input, args.output, config_path]
    if args.template:
        if not os.path.exists(args.template):
            print(f"Error: Template not found: {args.template}", file=sys.stderr)
            sys.exit(1)
        cmd.extend(["--template", args.template])

    ret = subprocess.run(cmd)
    sys.exit(ret.returncode)


if __name__ == "__main__":
    main()
