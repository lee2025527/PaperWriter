# r02 写作大脑:项目专属 prompt

对应流水线步骤 2。把角色、规则、题目、文献格式、需求单整合成单一"工作指令核" `output/work/prompt.md`。**硬约束:后续所有写作(综述/大纲/正文/摘要)开始前必须加载本文件。**

## 输入

- `$SKILL/templates/prompt_template.md`(模板,缺失则停下提示,不许徒手硬写)
- `$SKILL/references/writing-rules.md`(通用写作规则)
- `output/work/需求单.md`
- `output/work/文献详细列表.md`

## 生成

```bash
python3 "$SKILL/scripts/writing-prompt-builder/scripts/build_prompt.py" \
  --template "$SKILL/templates/prompt_template.md" \
  --requirements output/work/需求单.md \
  --literature output/work/文献详细列表.md \
  --rules "$SKILL/references/writing-rules.md" \
  --output output/work/prompt.md
```

## 校验(必须通过)

```bash
python3 "$SKILL/scripts/writing-prompt-builder/scripts/validate_prompt.py" \
  --template "$SKILL/templates/prompt_template.md" \
  --requirements output/work/需求单.md \
  --literature output/work/文献详细列表.md \
  --rules "$SKILL/references/writing-rules.md" \
  --output output/work/prompt.md
```

校验失败 → 修正需求单或文献列表后重新生成,最多自修复 2 次。

## 复核要点

- 题目、字数、查重/AIGC 要求、引用规范与需求单一致;
- 参考文献列表来自 `文献详细列表.md`,无编造;
- 明确"必须遵循写作规则(writing-rules)";
- 信息有限时也要输出**完整可执行**的 prompt,绝不把"待确认"写进 prompt 正文(补充点另行记录)。
