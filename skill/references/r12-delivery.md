# r12 图表注入、终检与交付

对应流水线步骤 12–13。把图表资产高保真注入 Word,完成终检,输出最终初稿与交付摘要。

## 一、定稿转 Word(以字数达标版为内容基准)

```bash
# 无模板
python3 "$SKILL/scripts/academic-markdown-to-docx/scripts/run_convert.py" \
  --input output/work/正文_字数达标版.md \
  --output output/deliver/论文初稿_定稿.docx
# 有学校模板
python3 "$SKILL/scripts/markdown_to_word_with_template/scripts/convert.py" \
  --input output/work/正文_字数达标版.md \
  --template "input/<模板.docx>" \
  --output output/deliver/论文初稿_定稿.docx
```

## 二、图表注入(AFTF 引擎)

```bash
python3 "$SKILL/scripts/universal-docx-figure-inserter/scripts/inserter_v2.py" \
  --docx output/deliver/论文初稿_定稿.docx \
  --assets "output/deliver/论文图表" \
  --config "$SKILL/scripts/universal-docx-figure-inserter/config/default_styles.yaml"
```

引擎行为:XML 深度拷贝保真插入(合并单元格/样式不丢)、按 ID+关键词模糊匹配占位符与资产、题注"图下表上"自动编号、生成 `output/work/insertion_report.json` 审计报告、缺失项在 Word 中红色高亮标记。

## 三、终检清单(QA)

1. `insertion_report.json` 无失败项,或失败项已列入交付摘要;
2. 引用终检:正文引用与文末列表一一对应(抽查 + 脚本);
3. 字数报告:目标 vs 实际;
4. 目录域存在([TOC] 已转 Word 目录,提醒用户打开后"更新域");
5. 中英文摘要与关键词齐全;
6. [待核验] 项全部收集;
7. 系统先行项目:`work/<系统交付目录>/` 在交付清单中。

## 四、交付摘要(必须输出给用户)

1. **产物清单**:`output/deliver/` 下全部文件(初稿定稿 docx、图表包、[系统先行]系统源码目录与运行入口);
2. **字数报告**:目标 vs 实际,各章分配表;
3. **引用统计**:文献总数、正文引用数、一致性结论;
4. **[待核验] 项汇总**:默认假设清单 + 生成数据清单 + 需索要材料清单——用户必须自行核实/替换的内容,逐条列出;
5. **人工润色重点建议**:2–4 条(如哪章论证最薄、哪些图建议换真实截图)。

## 输出

- `output/deliver/论文初稿_定稿.docx`
- `output/deliver/论文图表/`
- `output/work/QA_终检记录.md`(终检清单结果)
- 交付摘要(对话输出,同时落盘 `output/deliver/交付摘要.md`)
