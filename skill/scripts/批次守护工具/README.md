> 注:下述 `scripts/…` 路径相对 PaperWriter 技能目录(即 SKILL.md 所在目录)解析;在用户项目目录下执行命令时请使用技能实际安装路径。

# 批次守护工具（Batch Guard）

用于解决“批次写作过程中丢失内容 / 口头报完成但文件不齐全”的问题，提供 **批次产物硬校验** + **确定性合并**。

## 核心理念

- 以 `output/work/thesis_writing_plan.md` 中的 **Batch Manifest（YAML）** 为唯一权威来源（更稳定、可机器解析）。
- “完成”必须以 **文件落盘 + 非空 + 字数阈值 +（可选）承接摘要/覆盖点** 为证据。
- 合并稿由工具 **确定性生成**（按批次文件顺序拼接），避免人工合并遗漏。

## 使用方式

### 1) 批次产物校验（推荐每个 Batch 写完就跑一次）

```bash
python3 scripts/批次守护工具/verify_batches.py \
  --plan output/work/thesis_writing_plan.md \
  --workdir output/work \
  --strict
```

默认批次文件名约定：`output/work/正文_Batch{N}.md`

### 2) 合并批次正文（通过校验后再合并）

```bash
python3 scripts/批次守护工具/merge_batches.py \
  --plan output/work/thesis_writing_plan.md \
  --workdir output/work \
  --output output/work/正文_合并_v1.md
```

### 3) 合并后校验（确保每个批次内容进入合并稿）

```bash
python3 scripts/批次守护工具/verify_merge.py \
  --plan output/work/thesis_writing_plan.md \
  --workdir output/work \
  --merged output/work/正文_合并_v1.md
```

## Batch Manifest（机器可读）要求

计划文件需包含 YAML fenced code block，顶层包含：

- `batch_manifest_version: 1`（兼容旧键 `auto_writer_batch_manifest_version: 1`）
- `batches: [...]`

每个 batch 至少包含：

- `index`（int，从 1 递增）
- `name`（str）
- `target_word_count`（int）
- `min_word_count`（int）
- 可选：`require_transition_summary`（bool，默认 true）
- 可选：`cover_chapters`（list[str]）
- 可选：`require_headings`（list[str]，用于强校验）

## 输出与退出码

- 校验通过：退出码 `0`
- 校验失败：退出码 `1`，并输出缺失清单与建议
