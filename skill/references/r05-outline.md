# r05 论文大纲

对应流水线步骤 5(纯写作)/系统先行项目在系统交付后执行。产出 `output/work/论文大纲.md` + `output/deliver/论文大纲.docx`。开始前加载 `output/work/prompt.md`。

## 输入

1. `output/work/prompt.md`
2. `output/work/需求单.md`(结构要求、质量目标)
3. `output/work/文献详细列表.md`(引用依据)
4. `output/work/文献综述.md`(研究切入点)
5. 可选:`output/work/系统需求与技术方案.md`、`work/<系统交付目录>/docs/测试报告.md`(系统先行项目——大纲的系统章必须映射真实系统模块)、对标论文分析材料

## 要求

- **结构优先服从需求单**:老师给了章节结构/模板,逐条对齐;没有则用学科通用结构(标注默认);
- 系统先行项目采用经典结构:绪论 → 相关技术 → 需求分析 → 系统设计 → 系统实现(对应真实模块与截图)→ 系统测试(对应真实测试记录)→ 总结展望;
- 每个小节必须包含三要素:**写作要点**(本节核心问题)、**主要内容**(写什么、怎么写)、**意义/作用**(与论文目标的关系);
- 章节字数分配遵循需求单;证据需求逐节标注(需要哪条数据/哪个图/哪个系统截图)。

## 守门

1. 大纲与需求单结构要求**逐条比对**,差异项要么修正要么在执行记录说明原因;
2. 系统先行项目:每个系统章节都能指到真实模块/测试记录来源;
3. 覆盖性:所有必写章节齐备(含中英文摘要、参考文献、致谢按需)。

## 输出 Word 版

```bash
# 无模板:先用默认配置
cp "$SKILL/scripts/文档格式转换工具/config_template.json" output/work/docx_config.json
python3 "$SKILL/scripts/文档格式转换工具/universal_md_to_docx.py" \
  output/work/论文大纲.md \
  output/deliver/论文大纲.docx \
  output/work/docx_config.json

# 有模板(--template 指向 input/ 中的学校模板)
python3 "$SKILL/scripts/文档格式转换工具/universal_md_to_docx.py" \
  output/work/论文大纲.md \
  output/deliver/论文大纲.docx \
  output/work/docx_config.json \
  --template "input/<模板.docx>"
```

## 约束

严禁编造文献/数据/案例;不删不改既有文件;大纲条目不空泛,每条可执行。
