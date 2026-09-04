# 图表规格清单字段说明 (figures_spec schema)

图表规格清单为 YAML 或 JSON，用于描述每张图/表的 id、类型、数据来源及类型相关参数。生成器根据 `type` 分发到对应实现。

## 顶层结构

```yaml
# 可选：项目级默认
output_dir: "output/work/正文插图与表格"
data_root: "."   # 解析 data_path 时的根目录（相对路径基于此）

# 必选：图表项列表
items:
  - id: "图3-1"
    title: "上传检测结果展示下载流程"
    type: flowchart
    data_source: "案例与数据文档 2.3 节"
    options: { ... }
  - id: "表7-1"
    title: "系统测试用例与执行结果"
    type: table
    data_source: "案例与数据文档 2.4 节"
    options: { ... }
```

## 单条图表项字段

| 字段 | 必选 | 类型 | 说明 |
|------|------|------|------|
| **id** | 是 | string | 与正文占位符一致，如 `图3-1`、`表7-1`。 |
| **title** | 是 | string | 图题/表题文本（不含「图 3-1」前缀时，生成器可自动拼接）。 |
| **type** | 是 | string | 见下方类型枚举。 |
| **data_source** | 推荐 | string | 数据来源描述或引用，便于追溯。 |
| **data_path** | 可选 | string | 真实数据文件路径（相对 `data_root` 或绝对路径），如 CSV、JSON。 |
| **options** | 可选 | object | 类型相关参数，见各类型说明。 |
| **manual** | 可选 | boolean | 若为 true，表示需人工完成（如截图），生成器仅产出说明文件。 |

## 类型 (type) 枚举

| type | 说明 | options 常见字段 |
|------|------|------------------|
| **flowchart** | 流程图 | `nodes`: [{label, sublabel?, color?}], `direction`: "horizontal" \| "vertical" |
| **architecture** | 架构图 | `layers`: [{title, subtitle?, color?, modules: [string]}], `arrows`? |
| **layout_sketch** | 页面布局示意 | `regions`: [{name, rect?, color?}] |
| **line_chart** | 折线图 | `series`: [{name, values}], `categories`/x 轴标签, `y_label`, `y2_label`? |
| **bar_chart** | 柱状图 | `categories`, `series`: [{name, values}] |
| **pie_chart** | 饼图 | `series`: [{name, value}] |
| **confusion_matrix** | 混淆矩阵 | `matrix`: [[a,b],[c,d]], `labels`: [x轴, y轴] 或 `data_path` 指向 CSV |
| **table** | 表格（Word） | `headers`: [], `rows**: [[cell,...]] 或 `data_path` |
| **screenshot_placeholder** | 需手动截图 | `manual: true`，可配 `instructions` 说明文件内容 |

## 文件名约定

- 图片：`{id}_{title}.png`，其中 id 如 `图3-1`，title 为短标题（可去空格/标点）。
- 表格：`{id}_{title}.docx` 或 `.xlsx`。
- 若 `manual: true`，可产出 `{id}_请手动截图说明.txt`。

## 示例片段

```yaml
items:
  - id: 图3-1
    title: 上传检测结果展示下载流程
    type: flowchart
    data_source: 案例与数据文档 2.3 功能与界面
    options:
      direction: horizontal
      nodes:
        - label: 上传图像
          sublabel: Upload Image
          color: "#4A90E2"
        - label: 检测推理
          sublabel: Detection
          color: "#50C878"
        - label: 结果展示
          sublabel: Display
          color: "#FF8C42"
        - label: 下载结果
          sublabel: Download
          color: "#9B59B6"

  - id: 图7-2
    title: 训练过程曲线（loss / mAP）
    type: line_chart
    data_source: results.csv
    data_path: system/runs/detect/experiments/train/melanoma/results.csv
    options:
      x_key: epoch
      series:
        - name: Total Loss
          expr: "train/box_loss + train/cls_loss + train/dfl_loss"
        - name: mAP50
          key: "metrics/mAP50(B)"
      y_label: Loss
      y2_label: mAP50
```
