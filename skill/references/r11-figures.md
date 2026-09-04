# r11 图表工厂

对应流水线步骤 11(正文中存在 `> [插入图X-X:…]` / `> [插入表X-X:…]` 占位符时执行)。基于全文语境与 `案例与数据文档.md` 生成学术规范的图表资产,输出到 `output/deliver/论文图表/`。

## 流程

1. **占位符提取**:扫描 `正文_字数达标版.md` 全部图表占位符;可辅助:
   ```bash
   python3 "$SKILL/scripts/thesis-figure-table-generator/scripts/scan_placeholders.py"
   ```
2. **数据映射**:每个占位符关联案例与数据文档中的真实数据/流程/结构;系统先行项目的架构图、流程图对应真实系统模块,截图占位对应真实页面;
3. **渲染生成**(AcademicEngine,自适应 OS 中文字体):
   ```python
   import sys; sys.path.insert(0, "<$SKILL>/scripts/thesis-figure-table-generator/scripts")
   from core_engine import AcademicEngine
   from table_builder import AcademicTableBuilder
   engine = AcademicEngine("output/deliver/论文图表")
   tables = AcademicTableBuilder("output/deliver/论文图表")
   # 图:engine.draw_diagram("图2-1:业务流程", elements=[(x,y,w,h,"文本","style")...], arrows=[...])
   #    engine.draw_placeholder("图4-1:首页运行截图", "首页运行效果")  # 截图引导占位
   # 表:tables.create_table("表3-1:功能表", headers=[...], rows=[...])
   ```
4. **命名与规格**:图片 `图X-X：名称.png`(300 DPI,图内**无图题**——图题由 Word 步骤生成);表格 `表X-X：名称.docx`(可编辑纯净表格);文件名与占位符标题严格一致。

## 鲁棒性要求(必须)

- 图内严禁出现图题文字;
- 学术配色(Soft Blue / Purple / Green / Yellow),严禁高饱和杂乱配色;
- 中文字体必须在本机正常渲染,出现乱码方块即失败重渲;
- 截图占位图必须带明确引导文案:"请在此处插入 [具体页面名称] 运行截图";
- 系统先行项目:优先使用 r04 沉淀的真实截图,只有拿不到时才用引导占位。

## 守门

生成后逐文件检查:命名与占位符一一对应、可打开、无乱码、无图内图题;缺失项列入交付摘要。
