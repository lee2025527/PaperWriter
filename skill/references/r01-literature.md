# r01 文献阶段:清单优先,不足自动补检

对应流水线步骤 1。产出 `output/work/文献详细列表.md`。唯一可引用的文献来源,后续综述与正文只能引用本清单中的编号。

## 策略(三段式)

```
① input/ 或用户对话中有文献清单 → 全部收下
② 门槛判定:数量达标(需求单要求,默认≥15篇)且与选题相关?
③ 达标 → 直接整理输出,跳过检索
   不达标 → 自动检索,只补缺的部分(补检一轮)
```

判定"用户提供了文献"的标准:条目同时包含编号(如 `[1]`/`1.`)与年份(如 `2021`)。

## 一、统一入口(推荐,自动处理上述三段逻辑)

```bash
python3 "$SKILL/scripts/literature-detail-list/scripts/auto_literature_detail_list.py" \
  --input-dir input \
  --demand-file output/work/需求单.md \
  --output output/work/文献详细列表.md \
  --intermediate-dir output/work/文献检索中间产物 \
  --pipeline-prefix 文献检索结果
```

## 二、自动检索与摘要增强(需要补检时)

从需求单提取:论文题目、中文关键词、英文关键词(含同义词/缩写)。

```bash
python3 "$SKILL/scripts/文献检索增强工具/run_literature_pipeline.py" \
  --topic="<论文题目>" \
  --keywords-zh="<中文关键词,逗号分隔>" \
  --keywords-en="<英文关键词,逗号分隔>" \
  --major="<专业>" \
  --max=18 \
  --keep-all-results \
  --output="文献检索结果"
# 输出统一写入 output/work/文献检索中间产物/
```

- 前置:SERPAPI_KEY 已配置(.env 或环境变量);OpenAlex 摘要增强免费,建议配置 OPENALEX_EMAIL 提速。
- 英文检索失败不阻塞:只做中文检索,再单独跑 Stage3 增强:
  ```bash
  python3 "$SKILL/scripts/文献检索增强工具/enrich_abstracts_stage3.py" \
    output/work/文献检索中间产物/文献检索结果_zh_openalex.json \
    --output-dir output/work/文献检索中间产物
  ```

## 三、筛选与输出

```bash
python3 "$SKILL/scripts/literature-detail-list/scripts/filter_literature.py" \
  output/work/文献检索中间产物/文献检索结果_zh_openalex_stage3.json \
  --output output/work/文献详细列表.md \
  --demand-file output/work/需求单.md \
  --input-dir input \
  --topic "<论文题目>" \
  --recent-years 5 \
  --min-abstract-length 120 \
  --min-count 10
```

- 筛选首要标准是**主题相关**;严格筛选不足 7 篇时脚本自动"捡漏"(放宽年份/摘要限制,仅要求主题相关,输出标注 `⚠️ 捡漏补充`)。
- Scholar 片段摘要必须标注"需人工核验"。

## 四、守门与停止条件

1. 数量校验:`文献详细列表.md` 条目数 ≥ 需求单门槛(默认 15);
2. 相关性抽检:随机抽 5 条,标题/摘要与选题相关;
3. 数量不足 → 扩展关键词(加同义词/英文变体)自动补检**一轮**;
4. 补检后仍不足 → **停止,问人**:报告现有数量、已尝试的关键词,请用户补充文献或放宽门槛。

## 约束

- 不删除、不覆盖已有文件;中间产物保留在 `output/work/文献检索中间产物/` 供溯源。
- 严禁向清单中添加检索与用户清单之外"想象出来"的文献。
