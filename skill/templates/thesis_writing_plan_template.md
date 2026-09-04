# 毕业论文正文分阶段写作执行计划 (Thesis Writing Execution Plan - Template)

**目标**：基于《论文大纲》，产出高质量、逻辑连贯、数据真实的全篇论文。

**核心约束**：

1. **分批次写入**：严格控制单次输出长度，避免模型"遗忘"或截断。
2. **真人语感**：杜绝 AI 模版句式（如"综上所述"、"具有重要意义"）。
3. **数据闭环**：严格使用仿真或实验数据。

---

## 1. 写作前置准备 (Pre-writing Setup)

在开始任何写作之前，Agent 必须加载以下"上下文包"：

* **核**: `Universal_Writing_Rules.md` (最高准则)
* **脑**: `output/work/prompt.md` (角色、背景、文献库)
* **骨**: `output/work/论文大纲.md` (章节结构)
* **肉**: `output/work/客户诉求.md` & `output/work/文献综述.md` (具体方案)
* **血**: [INSERT DATA SOURCE PATH, e.g. output/simulation_data/] (真实证据)

---

## 2. 篇幅预算 (Word Count Budget)

**总目标**: [INSERT TOTAL WORD COUNT]字 (允许 ±10% 波动)。

| 批次 (Batch) | 包含章节 (Chapters) | 预估字数 (Estimated Words) | 核心内容 (Key Content) |
| :--- | :--- | :--- | :--- |
| **Batch 1** | 第1章 + 第2章 | **[INSERT COUNT] 字** | [INSERT KEY CONTENT] |
| **Batch 2** | 第3章 | **[INSERT COUNT] 字** | [INSERT KEY CONTENT] |
| **Batch 3** | 第4章 | **[INSERT COUNT] 字** | [INSERT KEY CONTENT] |
| **Batch 4** | 第5章 | **[INSERT COUNT] 字** | [INSERT KEY CONTENT] |
| **Batch 5** | 第6章 + 结论 | **[INSERT COUNT] 字** | [INSERT KEY CONTENT] |
| **Batch N** | 中英文摘要 | **600 字** | 中文摘要 + 中文关键词 + 英文摘要 + 英文关键词 |
| **Total** | **全文** | **[INSERT TOTAL] 字** | **符合学校要求** |

---

## 2.1 批次清单（机器可读 / Batch Manifest）

> 该区块用于工具解析与"是否写完"的硬校验，请保持 **YAML 语法正确**。
> 若你不确定字段怎么填，至少保证：`index`、`name`、`target_word_count`、`min_word_count` 存在且数值合理。

```yaml
batch_manifest_version: 1
batches:
  - index: 1
    name: "Batch 1: 引言与研究背景"
    cover_chapters: ["第1章", "第2章"]
    target_word_count: 2000
    min_word_count: 1600
    require_transition_summary: true
    key_points:
      - "明确研究背景与问题定义"
      - "给出研究目标、研究意义与结构安排"

  - index: 2
    name: "Batch 2: 研究方法/模型/流程"
    cover_chapters: ["第3章"]
    target_word_count: 2000
    min_word_count: 1600
    require_transition_summary: true
    key_points:
      - "方法流程可复现，变量/指标定义清晰"
      - "与数据来源/案例文档对齐"

  # ... 中间批次按实际大纲补充 ...

  - index: N
    name: "Batch N: 中英文摘要与关键词"
    cover_chapters: ["摘要"]
    target_word_count: 600
    min_word_count: 500
    require_transition_summary: false
    key_points:
      - "撰写中文摘要（约300字），采用四段式结构"
      - "列出中文关键词（3-5个）"
      - "撰写英文摘要（Abstract，约250词）"
      - "列出英文关键词（Keywords，3-5个）"
```

## 3. 分阶段写作批次 (Writing Batches)

### **Batch 1: [INSERT BATCH TITLE]**

* **覆盖章节**: [INSERT CHAPTER NUMBERS]
* **重点策略**:
  * [INSERT STRATEGY 1]
  * [INSERT STRATEGY 2]

### **Batch 2: [INSERT BATCH TITLE]**

* **覆盖章节**: [INSERT CHAPTER NUMBERS]
* **重点策略**:
  * [INSERT STRATEGY 1]
  * [INSERT STRATEGY 2]

... (以此类推，请根据大纲自行拆分)

### **Batch N: 中英文摘要与关键词**

* **覆盖章节**: 摘要
* **预估字数**: 600字
* **重点策略**:
  * **中文摘要**（约300字）：
    - 采用经典四段式结构：研究背景与目的 → 研究方法 → 研究结果 → 研究结论
    - 概括论文核心内容，突出研究特色
    - 说明技术方案与系统成果
    - 必须基于正文内容，不得出现正文中未涉及的内容
  * **中文关键词**（3-5个）：选择能准确反映论文主题的核心术语
  * **英文摘要**（Abstract，约250词）：与中文摘要对应，使用学术英语表达
  * **英文关键词**（Keywords，3-5个）：与中文关键词对应

---

## 4. 合并输出流程（必须严格遵守）

### 4.1 最终全文结构顺序

**合并时必须按以下顺序排列**：

1. **中文摘要** + 中文关键词
2. **英文摘要（Abstract）** + 英文关键词（Keywords）
3. **目录**（标记为 `[TOC]`，内容留空，后续由 Word 自动生成）
4. **正文第一章** 开始...
5. **参考文献**
6. **致谢**
7. **附录**（可选）

### 4.2 合并规则说明

* **摘要置顶**：中英文摘要必须位于全文最前面，在目录之前
* **目录占位**：目录位置标记为 `[TOC]`，内容留空，后续在 Word 中通过"更新域"自动生成
* **正文顺序**：目录之后才是第一章，依次往下

---

## 5. 质量控制流程 (QA Process)

每个 Batch 产出后，必须执行以下检查：

1. **AI 味嗅探 (Anti-AI Sniffer)**:
    * 检查是否有"本文旨在"、"综上所述"、"随着科技的发展"。
    * *对策*：发现一处，重写一段。
2. **逻辑连贯性检查 (Logic Chain)**:
    * 检查 Batch N 的参数是否与 Batch N-1 冲突。
3. **字数/篇幅核对 (Length Check)**:
    * 确保达到预设的详细程度。
4. **摘要一致性检查 (Abstract Consistency)**:
    * 检查摘要内容是否与正文一致。
    * 检查关键词是否在正文中出现。
5. **文献引用序号校验 (Citation Order Check)**（每批次写作结束时执行，**全文合并后必须再执行一次**）:
    * 扫描本批次正文中所有 `[n]` 引用，确认序号按**首次出现顺序从低到高**排列（`[1]`、`[2]`、`[3]`…不得跳号、乱序）。
    * 同一文献多次引用时，沿用首次出现时的编号，不重新编号。
    * 全文合并后，检查文末参考文献列表的排列顺序是否与正文首次出现顺序完全一致。
    * 文末列表仅保留正文中实际引用的文献，删除未被引用的条目。
    * *对策*：发现编号乱序或列表与正文不对应，立即重排，使用临时占位符法逐一替换，避免交叉替换错误。
    * **此规则为通用硬规则，适用于任何项目和领域，不得省略。**
