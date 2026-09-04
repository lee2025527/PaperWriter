# Prompt 模板字段映射说明

## 主要占位符
- [INSERT UNIVERSITY LEVEL]：默认“省属重点高校”。
- [INSERT MAJOR]：取自 `客户诉求.md` 的“专业”。
- [INSERT SKILL 1/2/3]：优先使用中文关键词前 3 个；不足则补“待补充”。
- [INSERT CHINESE TITLE]：取自“题目”。
- [INSERT ENGLISH TITLE]：若无，置为“待确认（如需英文题目请补充）”。
- [INSERT CORE FUNCTION DESCRIPTION]：优先使用“必须做”前三条拼接。
- [INSERT KEY TECH 1/2]：同技能词条（关键词前两项）。
- [INSERT WORD COUNT]：取自“字数”字段。
- [INSERT PERCENTAGE]（首次）：查重要求。
- [INSERT PERCENTAGE]（第二次）：AIGC 红线，默认 5。

## 文献列表插入
- 从 `文献详细列表.md` 的“引用列表区”读取，替换模板中中文文献占位。
- 若引用为空，保留“待补充”提示。

## 必读材料
- 自动附加存在的材料路径：
  - `output/work/客户诉求.md`
  - `output/work/文献详细列表.md`
  - `output/work/对标论文结构与写作标准解析.md`
  - `Universal_Writing_Rules.md`
