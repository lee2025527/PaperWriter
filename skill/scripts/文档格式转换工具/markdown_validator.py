#!/usr/bin/env python3
"""
Markdown 格式验证工具

用于在转换为 Word 前检查 Markdown 文件的格式规范性，
避免转换失败或格式错误。
"""

import re
import sys
import argparse
import json
from typing import List, Dict, Tuple
from pathlib import Path


class MarkdownValidator:
    """Markdown 格式验证器"""

    def __init__(self, md_path: str):
        self.md_path = md_path
        self.content = ""
        self.lines = []
        self.issues = []
        self.warnings = []
        self.info = []

        self.load_content()

    def load_content(self):
        """加载 Markdown 文件内容"""
        try:
            with open(self.md_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
                self.lines = self.content.split('\n')
        except FileNotFoundError:
            self.issues.append({
                "type": "file_not_found",
                "severity": "critical",
                "message": f"文件不存在: {self.md_path}"
            })
            raise

    def validate_all(self) -> Dict:
        """执行所有验证检查"""
        # 1. 检查标题层级
        self.check_heading_hierarchy()

        # 2. 检查图表占位符
        self.check_figure_placeholders()

        # 3. 检查特殊标记
        self.check_special_markers()

        # 4. 检查列表格式
        self.check_lists()

        # 5. 检查代码块
        self.check_code_blocks()

        # 6. 检查表格
        self.check_tables()

        # 7. 检查引用格式
        self.check_citations()

        return self.generate_report()

    def check_heading_hierarchy(self):
        """检查标题层级是否规范"""
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        headings = []

        for line_num, line in enumerate(self.lines, 1):
            match = heading_pattern.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                headings.append({
                    "line": line_num,
                    "level": level,
                    "title": title
                })

        # 检查层级跳跃
        if headings:
            prev_level = 0
            for h in headings:
                if h['level'] > prev_level + 1:
                    self.warnings.append({
                        "type": "heading_skip",
                        "line": h['line'],
                        "message": f"标题层级跳跃: H{prev_level} → H{h['level']}",
                        "current": f"H{h['level']}: {h['title']}",
                        "recommendation": f"应该在 H{prev_level} 和 H{h['level']} 之间插入 H{prev_level + 1}"
                    })
                prev_level = h['level']

        # 检查是否有 H1
        h1_count = sum(1 for h in headings if h['level'] == 1)
        if h1_count == 0:
            self.warnings.append({
                "type": "missing_h1",
                "message": "文档缺少一级标题 (H1)"
            })
        elif h1_count > 1:
            self.info.append({
                "type": "multiple_h1",
                "count": h1_count,
                "message": f"文档有 {h1_count} 个一级标题"
            })

    def check_figure_placeholders(self):
        """检查图表占位符格式"""
        # 标准格式: > [图表占位符 #序号: 标题 | 类型: xx | 数据来源: xx]
        standard_pattern = re.compile(
            r'>\s*\[图表占位符\s*#(\d+):\s*([^|]+)\s*\|\s*类型:\s*([^|]+)\s*\|\s*数据来源:\s*[^\]]+\]'
        )

        # 旧格式: > [插入图1：xxx]
        legacy_pattern = re.compile(r'>\s*\[插入(图|表)(\d+)[:：]\s*(.*?)\]')

        # 其他非标准引用
        invalid_pattern = re.compile(r'!\[.*?\]\(.*?\)')

        standard_count = 0
        legacy_count = 0
        invalid_refs = []

        for line_num, line in enumerate(self.lines, 1):
            # 检查标准格式
            if standard_pattern.search(line):
                standard_count += 1

            # 检查旧格式
            if legacy_pattern.search(line):
                legacy_count += 1
                self.warnings.append({
                    "type": "legacy_figure_format",
                    "line": line_num,
                    "message": "使用旧版图表格式",
                    "recommendation": "更新为标准格式: > [图表占位符 #序号: 标题 | 类型: xx | 数据来源: xx]"
                })

            # 检查可能的无效引用
            if invalid_pattern.search(line):
                invalid_refs.append(line_num)

        if invalid_refs:
            self.warnings.append({
                "type": "invalid_image_refs",
                "lines": invalid_refs,
                "message": f"发现 {len(invalid_refs)} 处可能的无效图片引用",
                "recommendation": "图片引用不会自动转换为图表，请使用图表占位符格式"
            })

        if standard_count > 0:
            self.info.append({
                "type": "figure_placeholders",
                "count": standard_count,
                "message": f"发现 {standard_count} 个标准图表占位符"
            })

    def check_special_markers(self):
        """检查特殊标记 (TOC, 分页符等)"""
        has_toc = '[TOC]' in self.content
        page_breaks = self.content.count('---')

        if not has_toc:
            self.warnings.append({
                "type": "missing_toc",
                "message": "文档缺少目录标记 [TOC]",
                "recommendation": "在需要目录的位置添加 [TOC]"
            })

        if page_breaks > 0:
            self.info.append({
                "type": "page_breaks",
                "count": page_breaks,
                "message": f"文档包含 {page_breaks} 个分页符标记 (---)"
            })

    def check_lists(self):
        """检查列表格式"""
        # 检查无序列表和有序列表
        unordered_pattern = re.compile(r'^(\s*)[-*+]\s+(.+)$')
        ordered_pattern = re.compile(r'^(\s*)\d+\.\s+(.+)$')

        list_errors = []

        for line_num, line in enumerate(self.lines, 1):
            # 检查列表项后的空行
            if unordered_pattern.match(line) or ordered_pattern.match(line):
                # 检查下一行是否是空行或同级别的列表项
                if line_num < len(self.lines):
                    next_line = self.lines[line_num]
                    if next_line.strip() and not unordered_pattern.match(next_line) and not ordered_pattern.match(next_line):
                        # 可能是列表和段落混在一起，但不一定是错误
                        pass

        # 检查列表嵌套深度（超过 4 层可能有问题）
        max_indent = 0
        for line in self.lines:
            match = unordered_pattern.match(line) or ordered_pattern.match(line)
            if match:
                indent = len(match.group(1))
                max_indent = max(max_indent, indent)

        if max_indent > 12:  # 超过 12 个空格 = 3 层嵌套
            self.info.append({
                "type": "deep_nesting",
                "max_spaces": max_indent,
                "message": f"列表最大嵌套深度: {max_indent // 4} 层"
            })

    def check_code_blocks(self):
        """检查代码块格式"""
        # 检查是否有未闭合的代码块
        fence_pattern = re.compile(r'^```')
        fence_count = 0

        for line in self.lines:
            if fence_pattern.match(line):
                fence_count += 1

        if fence_count % 2 != 0:
            self.issues.append({
                "type": "unclosed_code_block",
                "severity": "error",
                "message": "存在未闭合的代码块 (``` 标记不成对)",
                "recommendation": "确保每个代码块都有开始和结束标记"
            })

        # 统计代码块数量
        code_block_count = fence_count // 2
        if code_block_count > 0:
            self.info.append({
                "type": "code_blocks",
                "count": code_block_count,
                "message": f"文档包含 {code_block_count} 个代码块"
            })

    def check_tables(self):
        """检查表格格式"""
        # 简单检查：查找 Markdown 表格（包含 | 的行）
        table_lines = []
        in_table = False

        for line_num, line in enumerate(self.lines, 1):
            if '|' in line and line.strip():
                if not in_table:
                    in_table = True
                    table_lines.append(line_num)
                # 检查分隔行 (|---|---|)
                if re.search(r'\|[\s\-:]+\|', line):
                    pass
            else:
                if in_table and line.strip():
                    in_table = False

        table_count = len(set(
            ln - 1 for ln in table_lines
            if ln > 1 and '|' not in self.lines[ln - 2]
        ))

        if table_count > 0:
            self.info.append({
                "type": "tables",
                "count": table_count,
                "message": f"文档包含约 {table_count} 个表格"
            })

    def check_citations(self):
        """检查引用格式"""
        # 查找 [数字] 格式的引用
        citation_pattern = re.compile(r'\[(\d+)\]')
        citations = citation_pattern.findall(self.content)

        if citations:
            # 检查引用是否连续
            citation_numbers = [int(c) for c in set(citations)]
            citation_numbers.sort()

            if citation_numbers:
                # 检查是否有缺失的引用编号
                missing = []
                for i in range(1, max(citation_numbers) + 1):
                    if i not in citation_numbers:
                        missing.append(i)

                if missing:
                    self.issues.append({
                        "type": "missing_citation_numbers",
                        "severity": "warning",
                        "message": f"引用编号不连续，缺失: {missing[:5]}{'...' if len(missing) > 5 else ''}",
                        "recommendation": "检查正文中是否有遗漏的引用编号"
                    })

                self.info.append({
                    "type": "citations",
                    "count": len(set(citations)),
                    "max_number": max(citation_numbers),
                    "message": f"文档包含 {len(set(citations))} 个引用，最大编号: [{max(citation_numbers)}]"
                })

    def generate_report(self) -> Dict:
        """生成验证报告"""
        return {
            "file": self.md_path,
            "status": "passed" if not self.issues else "failed",
            "summary": {
                "critical_issues": len([i for i in self.issues if i.get("severity") == "critical"]),
                "errors": len(self.issues),
                "warnings": len(self.warnings),
                "info": len(self.info)
            },
            "issues": self.issues,
            "warnings": self.warnings,
            "info": self.info
        }

    def print_report(self):
        """打印格式化的报告"""
        report = self.generate_report()

        print("\n" + "=" * 60)
        print("Markdown 格式验证报告")
        print("=" * 60)
        print(f"文件: {self.md_path}")
        print(f"状态: {report['summary']['errors']} 个错误, {report['summary']['warnings']} 个警告\n")

        if report['summary']['critical_issues'] > 0:
            print(f"🚨 严重问题: {report['summary']['critical_issues']}")
            for issue in self.issues:
                if issue.get("severity") == "critical":
                    print(f"   • {issue['message']}")

        if self.issues:
            print(f"\n❌ 错误 ({len(self.issues)}):")
            for issue in self.issues:
                line_info = f" (行 {issue.get('line', '?')})" if 'line' in issue else ""
                print(f"   • {issue['message']}{line_info}")
                if issue.get('recommendation'):
                    print(f"     建议: {issue['recommendation']}")

        if self.warnings:
            print(f"\n⚠️  警告 ({len(self.warnings)}):")
            for warning in self.warnings[:10]:  # 显示前 10 个
                line_info = f" (行 {warning.get('line', '?')})" if 'line' in warning else ""
                print(f"   • {warning['message']}{line_info}")
                if warning.get('recommendation'):
                    print(f"     建议: {warning['recommendation']}")
            if len(self.warnings) > 10:
                print(f"   ... 还有 {len(self.warnings) - 10} 个警告")

        if self.info:
            print(f"\nℹ️  信息 ({len(self.info)}):")
            for info in self.info[:5]:
                print(f"   • {info['message']}")
            if len(self.info) > 5:
                print(f"   ... 还有 {len(self.info) - 5} 条信息")

        print("\n" + "=" * 60)

        if report['status'] == "passed":
            print("✅ 格式验证通过！可以转换为 Word。")
        else:
            print("❌ 发现问题，建议修复后再转换。")

        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Markdown 格式验证工具 - 在转换为 Word 前检查格式规范性"
    )
    parser.add_argument("input_md", help="输入的 Markdown 文件路径")
    parser.add_argument("--output", "-o", help="保存验证报告到 JSON 文件")
    parser.add_argument("--strict", action="store_true",
                        help="严格模式：有任何错误就返回非零退出码")

    args = parser.parse_args()

    try:
        validator = MarkdownValidator(args.input_md)
        report = validator.validate_all()
        validator.print_report()

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"详细报告已保存至: {args.output}\n")

        if args.strict and report['status'] == "failed":
            sys.exit(1)

    except FileNotFoundError:
        print(f"错误: 文件不存在 - {args.input_md}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
