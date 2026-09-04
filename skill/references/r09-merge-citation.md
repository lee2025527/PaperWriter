# r09 合并、引用治理与初稿转 Word

对应流水线步骤 9。把全部批次变成一份**纯净、引用对齐**的合并稿,并产出第一版 Word 初稿。

## 一、合并与净化(优先用脚本)

```bash
python3 "$SKILL/scripts/批次守护工具/merge_clean.py"
```
默认读取 `output/work/正文_Batch1.md`~`BatchN.md`,按"摘要置顶 → [TOC] → 正文各章 → 参考文献 → 致谢"顺序输出 `output/work/正文_合并_v1.md`,并自动剔除各批"## 批次承接摘要"及其后内容。

合并后覆盖校验(确保每批内容都进入了合并稿):

```bash
python3 "$SKILL/scripts/批次守护工具/verify_merge.py" \
  --plan output/work/thesis_writing_plan.md \
  --workdir output/work \
  --merged output/work/正文_合并_v1.md
```

若手工合并:严格按计划顺序拼接,删除所有"批次承接摘要"节,保留完整图表占位符。

## 二、引用治理(必须执行)

目标:正文引用序号按**首次出现顺序**连续([1]、[2]…),文末列表与之一一对应,仅列被引文献,格式 GB/T 7714-2015。

算法:
1. 扫描正文(不含摘要、致谢)所有 `[n]`,按首次出现顺序得编号序列;
2. 建立旧→新编号映射(临时占位符中转,避免交叉替换错误);
3. 全文替换为新编号;
4. 重写文末「参考文献」:按新序号排列,条目内容取自 `文献详细列表.md`,仅含实际被引文献;
5. 未被引用的文献不出现在列表中。

辅助脚本(Word 产物阶段也可用):
```bash
python3 "$SKILL/scripts/reference-citation-optimizer/reorder_by_first_appearance.py"   # Markdown 引用重排
python3 "$SKILL/scripts/文档格式转换工具/reorder_references_by_citation.py"            # docx 引用列表重排
```

**约束**:不得编造或新增文献详细列表之外的文献;引用与列表无缺号、无多余。

## 三、初稿转 Word

- 无模板(学术中文经典排版):
  ```bash
  python3 "$SKILL/scripts/academic-markdown-to-docx/scripts/run_convert.py" \
    --input output/work/正文_合并_v1.md \
    --output output/deliver/论文初稿_v1.docx
  ```
- 有学校模板(`--template` 必填场景):
  ```bash
  python3 "$SKILL/scripts/markdown_to_word_with_template/scripts/convert.py" \
    --input output/work/正文_合并_v1.md \
    --template "input/<模板.docx>" \
    --output output/deliver/论文初稿_v1.docx
  ```

Markdown 约定:标题 `#`~`####`;`[TOC]` 独占一行(Word 目录域,打开后"更新域"出页码);`---` 独占一行=分页;`## 参考文献` 后的 `[n]` 段落按参考文献样式渲染;列表用 `* `。

## 守门

verify_merge.py 通过 + 引用抽查 10 处无错位 + docx 能打开且无乱码。
