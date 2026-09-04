#!/usr/bin/env python3
"""
优化版学术文献检索工具 - v5.0
新增特性：智能批次、质量筛选、相关搜索利用

版本: v5.0 - 智能优化版
日期: 2025-01-21
"""

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

class OptimizedLiteratureSearch:
    """高性能学术文献搜索引擎 - v5.0"""

    def __init__(
        self,
        api_key: str,

        # === 基础参数 ===
        hl: str = "",
        lr: str = "",
        timeout: int = 30,
        abstract_limit: int = 1200,
        ca_bundle: str = "",

        # === API调用参数 ===
        num_per_call: int = 20,              # 每次请求的最大数量
        accept_variable_results: bool = True, # 接受实际返回的任何数量

        # === 质量筛选参数 ===
        min_quality_score: int = 60,        # 最低质量分数
        use_quality_filter: bool = True,    # 启用质量筛选

        # === 多轮控制参数 ===
        max_rounds: int = 3,                 # 最大轮数限制

        # === 智能停止参数 ===
        stop_when_target_met: bool = True,   # 达标后停止
        stop_quality_threshold: int = 75,   # 停止质量阈值

        # === 无目标模式参数 ===
        no_target_mode_rounds: int = 1,     # 无目标时的默认轮数

        # === 相关搜索参数 ===
        use_related_searches: bool = True,   # 使用相关搜索补充
        max_related_queries: int = 1,        # 最多使用N个相关搜索
    ):
        """初始化搜索引擎"""
        self.api_key = api_key
        self.default_hl = hl
        self.default_lr = lr
        self.timeout = timeout
        self.abstract_limit = abstract_limit
        self.ca_bundle = ca_bundle or os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE")
        self.base_url = "https://serpapi.com/search.json"

        # 新增参数
        self.num_per_call = num_per_call
        self.accept_variable_results = accept_variable_results
        self.min_quality_score = min_quality_score
        self.use_quality_filter = use_quality_filter
        self.max_rounds = max_rounds
        self.stop_when_target_met = stop_when_target_met
        self.stop_quality_threshold = stop_quality_threshold
        self.no_target_mode_rounds = no_target_mode_rounds
        self.use_related_searches = use_related_searches
        self.max_related_queries = max_related_queries

        # 兼容旧参数
        self.overfetch_factor = 1
        self.round_fetch_limit = num_per_call
        self.max_search_rounds = max_rounds
        self.result_threshold_ratio = 0.8
        self.max_rounds_per_language = 2

        # 统计信息
        self.search_stats = {
            'papers_found': 0,
            'search_time': 0,
            'keywords_processed': 0,
            'api_requests': 0,
            'pages_fetched': 0,
            'search_rounds': 0,
            'search_strategy': 'smart_optimized_v5'
        }

        # 相关搜索存储
        self._last_related_searches: List[str] = []

    def _contains_cjk(self, text: str) -> bool:
        """检测是否包含中文字符"""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False

    def _detect_language(self, text: str) -> str:
        """根据文本粗略判断语言"""
        return "zh-CN" if self._contains_cjk(text) else "en"

    def _serpapi_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """调用 SerpAPI 并返回 JSON 结果"""
        if not self.api_key:
            raise ValueError("缺少 SerpAPI KEY")

        query_params = dict(params)
        query_params["api_key"] = self.api_key

        url = f"{self.base_url}?{urllib.parse.urlencode(query_params)}"
        try:
            context = None
            if self.ca_bundle:
                context = ssl.create_default_context(cafile=self.ca_bundle)
            with urllib.request.urlopen(url, timeout=self.timeout, context=context) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"SerpAPI HTTP 错误: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"SerpAPI 连接失败: {exc.reason}") from exc

        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"SerpAPI 返回错误: {data['error']}")

        return data

    def _extract_year(self, text: str) -> Optional[int]:
        """提取年份"""
        match = re.search(r"\b(19|20)\d{2}\b", text or "")
        if match:
            return int(match.group(0))
        return None

    def _extract_authors(self, publication_info: Dict[str, Any]) -> List[str]:
        """提取作者信息"""
        authors = []
        raw_authors = publication_info.get("authors") or []
        for author in raw_authors:
            if isinstance(author, dict):
                name = author.get("name")
            else:
                name = str(author)
            if name:
                authors.append(name.strip())

        if authors:
            return authors

        summary = publication_info.get("summary", "")
        if not summary:
            return []

        head = summary.split(" - ")[0].replace("…", "")
        candidates = [item.strip() for item in head.split(",") if item.strip()]
        cleaned = [item for item in candidates if not re.search(r"\d", item)]
        return cleaned or candidates

    def _extract_pdf_url(self, resources: Any) -> str:
        """提取PDF链接"""
        for resource in resources or []:
            if str(resource.get("file_format", "")).upper() == "PDF":
                return resource.get("link", "")
        return ""

    def _score_result(self, year: Optional[int], cited_by: Optional[int], title: str) -> int:
        """计算文献质量评分"""
        score = 50

        if year:
            if year >= 2023:
                score += 25
            elif year >= 2020:
                score += 15
            elif year >= 2017:
                score += 5

        if cited_by:
            if cited_by >= 1000:
                score += 20
            elif cited_by >= 200:
                score += 15
            elif cited_by >= 50:
                score += 10
            elif cited_by >= 10:
                score += 5

        if any(word in title.lower() for word in ['design', 'analysis', 'optimization', 'model', 'method', 'study']):
            score += 10

        return min(score, 100)

    def _parse_scholar_result(self, result: Dict[str, Any], query: str) -> Optional[Dict[str, Any]]:
        """解析单个搜索结果"""
        title = (result.get("title") or "").strip()
        if not title:
            return None

        publication_info = result.get("publication_info") or {}
        summary = (publication_info.get("summary") or "").strip()
        authors = self._extract_authors(publication_info)
        year = self._extract_year(summary) or self._extract_year(result.get("snippet", ""))
        abstract = (result.get("snippet") or "").strip()
        pdf_url = self._extract_pdf_url(result.get("resources"))
        cited_by = (result.get("inline_links") or {}).get("cited_by", {}).get("total")

        paper = {
            'title': title,
            'authors': authors,
            'year': year,
            'abstract': abstract[:self.abstract_limit],
            'url': result.get("link") or "",
            'source': 'Google Scholar',
            'search_keyword': query,
            'publication_summary': summary,
            'cited_by': cited_by,
            'pdf_url': pdf_url,
            'result_id': result.get("result_id")
        }

        paper['enhanced_score'] = self._score_result(year, cited_by, title)
        return paper

    def _single_api_call(
        self,
        query: str,
        num: int = 20,
        start: int = 0,
        hl: str = ""
    ) -> List[Dict[str, Any]]:
        """
        单次API调用

        关键特性：
        - 设置 num=20（或接近20）
        - 接受实际返回的任何数量（0-20条）
        - 抓取所有实际返回的结果
        - 保存相关搜索信息
        """
        # 确保不超过 SerpAPI 限制
        actual_num = min(num, 20)

        # 构建参数
        params: Dict[str, Any] = {
            "engine": "google_scholar",
            "q": query,
            "start": start,
            "num": actual_num
        }

        if hl:
            params["hl"] = hl
        if self.default_lr:
            params["lr"] = self.default_lr

        # 执行API调用
        try:
            data = self._serpapi_request(params)
            self.search_stats['api_requests'] += 1
            self.search_stats['pages_fetched'] += 1
        except Exception as exc:
            print(f"   ❌ API调用失败: {exc}")
            return []

        # 解析所有实际返回的结果
        organic_results = data.get("organic_results", [])
        actual_count = len(organic_results)

        papers = []
        for item in organic_results:
            paper = self._parse_scholar_result(item, query)
            if paper:
                papers.append(paper)

        # 记录实际返回量
        print(f"   📥 API返回: {actual_count} 条 (请求{actual_num}条)")

        # 保存相关搜索（如果启用）
        if self.use_related_searches:
            self._save_related_searches(data.get("related_searches", []))

        return papers

    def _save_related_searches(self, related_searches: List[Dict]) -> None:
        """保存相关搜索信息"""
        self._last_related_searches = [
            item.get("query", "")
            for item in related_searches
            if item.get("query")
        ]

    def _get_related_searches(self) -> List[str]:
        """获取保存的相关搜索"""
        return getattr(self, '_last_related_searches', [])

    def _filter_by_quality(
        self,
        papers: List[Dict[str, Any]],
        min_score: int = None
    ) -> List[Dict[str, Any]]:
        """按质量筛选文献"""
        if not self.use_quality_filter:
            return papers

        min_score = min_score or self.min_quality_score
        qualified = [p for p in papers if p.get('enhanced_score', 50) >= min_score]
        return qualified

    def _build_full_query(
        self,
        base_query: str,
        major: str = "",
        direction: str = ""
    ) -> str:
        """构建完整查询"""
        terms: List[str] = []

        if base_query:
            terms.append(base_query.strip())

        if major:
            terms.append(major.strip())

        if direction:
            terms.append(direction.strip())

        # 去重
        seen = set()
        unique_terms = []
        for term in terms:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                unique_terms.append(term)

        return " ".join(unique_terms)

    def _should_stop_search(
        self,
        results: List[Dict[str, Any]],
        target_count: int,
        round_idx: int = 0
    ) -> Tuple[bool, str]:
        """
        判断是否应该停止搜索

        Returns:
            (should_stop, reason)
        """
        if not results:
            return False, ""

        # 基础统计
        current_count = len(results)
        scores = [r.get('enhanced_score', 50) for r in results]
        avg_score = sum(scores) / len(scores)
        high_quality_count = sum(1 for s in scores if s >= self.stop_quality_threshold)

        # 规则1：数量达标 + 质量优秀
        if current_count >= target_count and avg_score >= self.stop_quality_threshold:
            return True, f"✅ 数量达标({current_count})且质量优秀({avg_score:.1f}分)"

        # 规则2：数量接近 + 高质量占比高
        if current_count >= target_count * 0.9 and high_quality_count >= target_count * 0.8:
            return True, f"✅ 数量接近({current_count}/{target_count})且高质量占比高({high_quality_count}/{current_count})"

        # 规则3：达到最大轮数
        if round_idx >= self.max_rounds - 1:
            return True, f"⏹️ 达到最大轮数({self.max_rounds})"

        # 规则4：超额较多
        if current_count >= target_count * 1.5 and avg_score >= 65:
            return True, f"✅ 数量充足({current_count})，停止搜索"

        return False, f"继续搜索...当前: {current_count}/{target_count}, 质量: {avg_score:.1f}分"

    def search(
        self,
        query: str,
        max_results: int = 0,  # 0表示无目标
        hl: str = "",
        major: str = "",
        direction: str = ""
    ) -> List[Dict[str, Any]]:
        """
        统一的搜索入口

        Args:
            query: 搜索查询
            max_results: 目标数量（0或负数=无目标）
            hl: 语言设置
            major: 专业领域
            direction: 研究方向

        Returns:
            文献列表（已按质量评分排序）
        """
        print(f"\n{'='*60}")
        print(f"🔍 开始搜索")
        print(f"   查询: {query}")
        print(f"   目标: {max_results if max_results > 0 else '无目标（最大化获取）'}")
        print(f"{'='*60}\n")

        # 场景分发
        if max_results <= 0:
            # 无目标：默认1次API调用，最大化筛选
            return self._search_without_target(query, hl, major, direction)
        else:
            # 有目标：多次调用直到达标
            return self._search_with_target(query, max_results, hl, major, direction)

    def _search_with_target(
        self,
        query: str,
        target_count: int,
        hl: str = "",
        major: str = "",
        direction: str = ""
    ) -> List[Dict[str, Any]]:
        """有明确目标的搜索"""

        # 筛选池
        raw_pool: List[Dict[str, Any]] = []
        seen_titles: set = set()

        print(f"🎯 目标模式：需要 {target_count} 篇合格文献(≥{self.min_quality_score}分)")
        print(f"⏱️ 最大轮数：{self.max_rounds}\n")

        for round_idx in range(self.max_rounds):
            print(f"{'─'*60}")
            print(f"📍 第 {round_idx + 1} 轮API调用")
            print(f"{'─'*60}")

            # 构建查询
            full_query = self._build_full_query(query, major, direction)

            # 尝试使用相关搜索（第2轮及以后）
            if round_idx > 0 and self.use_related_searches:
                related_searches = self._get_related_searches()
                if related_searches and len(related_searches) > round_idx - 1:
                    related_query = related_searches[round_idx - 1]
                    print(f"   💡 使用相关搜索: {related_query}")
                    full_query = related_query

            # 执行API调用（num=20，但接受实际返回量）
            papers_batch = self._single_api_call(
                query=full_query,
                num=self.num_per_call,
                hl=hl
            )

            # 如果没返回任何结果
            if not papers_batch:
                print(f"   ⚠️ 本轮未获取到任何结果")
                print(f"   ➡️ 可能原因：查询过于具体或无相关文献")
                print(f"   ➡️ 建议：尝试使用更通用的关键词")
                print(f"   ⏹️ 停止搜索\n")
                break

            # 去重并全部加入筛选池
            new_papers = 0
            for paper in papers_batch:
                title_key = paper['title'].lower().replace(' ', '')[:80]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    raw_pool.append(paper)
                    new_papers += 1

            print(f"   ➕ 筛选池新增: {new_papers} 篇")
            print(f"   📊 筛选池总量: {len(raw_pool)} 篇\n")

            # 从筛选池中筛选合格文献
            qualified_papers = self._filter_by_quality(raw_pool)

            print(f"   🎯 质量筛选:")
            print(f"      筛选池总量: {len(raw_pool)} 篇")
            print(f"      合格文献(≥{self.min_quality_score}分): {len(qualified_papers)} 篇")
            print(f"      目标数量: {target_count} 篇")

            # 显示质量统计
            if raw_pool:
                scores = [p.get('enhanced_score', 50) for p in raw_pool]
                avg_score = sum(scores) / len(scores)
                high_quality = sum(1 for s in scores if s >= 70)
                very_high_quality = sum(1 for s in scores if s >= 80)
                print(f"\n   📈 质量分布:")
                print(f"      平均分: {avg_score:.1f}")
                print(f"      高质量(≥70): {high_quality} 篇 ({high_quality/len(raw_pool)*100:.1f}%)")
                print(f"      优秀(≥80): {very_high_quality} 篇 ({very_high_quality/len(raw_pool)*100:.1f}%)")

            print()

            # 判断是否达标
            should_stop, reason = self._should_stop_search(
                raw_pool, target_count, round_idx
            )

            if should_stop:
                print(f"   {reason}")
                if "达到最大轮数" in reason and len(qualified_papers) < target_count:
                    print(f"   ⚠️ 未达到目标数量 ({len(qualified_papers)} < {target_count})")
                print(f"   ⏹️ 停止搜索\n")
                break
            else:
                print(f"   {reason}")
                if "继续搜索" in reason:
                    needed = target_count - len(qualified_papers)
                    print(f"   ⚠️ 还需要 {needed} 篇合格文献")
                print()

        # 最终处理：从筛选池中取出前 N 篇最高质量的
        qualified_papers = self._filter_by_quality(raw_pool)
        qualified_papers.sort(key=lambda x: x.get('enhanced_score', 50), reverse=True)

        final_result = qualified_papers[:target_count]

        # 总结报告
        print(f"{'='*60}")
        print(f"✅ 搜索完成")
        print(f"   最终返回: {len(final_result)} 篇（目标 {target_count} 篇）")
        print(f"   API调用次数: {round_idx + 1} 次")
        print(f"   筛选池总量: {len(raw_pool)} 篇")
        if final_result:
            final_scores = [p.get('enhanced_score', 50) for p in final_result]
            print(f"   平均质量: {sum(final_scores)/len(final_result):.1f} 分")
        print(f"{'='*60}\n")

        return final_result

    def _search_without_target(
        self,
        query: str,
        hl: str = "",
        major: str = "",
        direction: str = "",
        specified_rounds: int = None
    ) -> List[Dict[str, Any]]:
        """无明确目标的搜索"""

        # 确定调用次数
        rounds = specified_rounds if specified_rounds is not None else self.no_target_mode_rounds

        print(f"🎯 无目标模式：最大化筛选")
        print(f"⏱️ 调用次数：{rounds} 次\n")

        # 筛选池
        raw_pool: List[Dict[str, Any]] = []
        seen_titles: set = set()

        for round_idx in range(rounds):
            print(f"{'─'*60}")
            print(f"📍 第 {round_idx + 1} 轮API调用")
            print(f"{'─'*60}")

            # 构建查询
            full_query = self._build_full_query(query, major, direction)

            # 执行API调用
            papers = self._single_api_call(
                query=full_query,
                num=self.num_per_call,
                hl=hl
            )

            # 如果没返回任何结果
            if not papers:
                print(f"   ⚠️ 本轮未获取到任何结果")
                if round_idx == 0:
                    print(f"   ➡️ 查询可能过于具体，建议使用更通用的关键词")
                else:
                    print(f"   ➡️ 尝试其他查询仍无结果，停止搜索")
                break

            # 去重并加入筛选池
            new_papers = 0
            for paper in papers:
                title_key = paper['title'].lower().replace(' ', '')[:80]
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    raw_pool.append(paper)
                    new_papers += 1

            print(f"   ➕ 筛选池新增: {new_papers} 篇")
            print(f"   📊 筛选池总量: {len(raw_pool)} 篇\n")

        # 质量筛选
        print(f"{'─'*60}")
        print(f"📍 质量筛选")
        print(f"{'─'*60}")

        qualified_papers = self._filter_by_quality(raw_pool)

        print(f"      筛选阈值: ≥{self.min_quality_score} 分")
        print(f"      原始数量: {len(raw_pool)} 篇")
        print(f"      合格数量: {len(qualified_papers)} 篇")

        if raw_pool:
            scores = [p.get('enhanced_score', 50) for p in raw_pool]
            avg_score = sum(scores) / len(scores)
            high_quality = sum(1 for s in scores if s >= 70)
            print(f"      平均质量: {avg_score:.1f} 分")
            print(f"      高质量(≥70): {high_quality} 篇")

        # 按质量排序
        qualified_papers.sort(key=lambda x: x.get('enhanced_score', 50), reverse=True)

        print()
        print(f"{'='*60}")
        print(f"✅ 搜索完成")
        print(f"   最终返回: {len(qualified_papers)} 篇")
        print(f"   API调用次数: {rounds} 次")
        if qualified_papers:
            final_scores = [p.get('enhanced_score', 50) for p in qualified_papers]
            print(f"   平均质量: {sum(final_scores)/len(qualified_papers):.1f} 分")
        print(f"{'='*60}\n")

        return qualified_papers

    # === 兼容旧接口的方法 ===

    def search_literature(self, topic: str, keywords: str, major: str = "",
                         direction: str = "", max_results: int = 18) -> Dict[str, Any]:
        """主要搜索接口（兼容旧版本）"""

        # 将逗号分隔的关键词转换为列表
        keyword_list = [k.strip() for k in keywords.split(',') if k.strip()] if keywords else []

        # 构建查询
        query = self._build_full_query(topic, major, direction)

        # 执行搜索
        papers = self.search(
            query=query,
            max_results=max_results,
            hl=self.default_hl or self._detect_language(keywords or topic)
        )

        # 生成输出格式（兼容旧版本）
        citations = self.format_citations(papers)

        scores = [p['enhanced_score'] for p in papers]
        quality_dist = {
            'excellent': sum(1 for s in scores if s >= 80),
            'good': sum(1 for s in scores if 60 <= s < 80),
            'fair': sum(1 for s in scores if 40 <= s < 60),
            'poor': sum(1 for s in scores if s < 40)
        }

        return {
            "search_metadata": {
                "search_time": datetime.now().isoformat(),
                "optimization_version": "v5.0",
                "engine": "google_scholar",
                "query": query,
                "input": {
                    'topic': topic,
                    'keywords': keywords,
                    'major': major,
                    'direction': direction
                },
                "search_statistics": self.search_stats,
                "search_strategy": "smart_optimized_v5"
            },
            "search_results": {
                "total_literature_found": len(papers),
                "papers": papers,
                "formatted_citations": citations,
                "quality_summary": {
                    "average_score": sum(scores) / len(scores) if scores else 0,
                    "score_distribution": quality_dist,
                    "performance_metrics": {
                        "search_time_seconds": round(self.search_stats['search_time'], 1),
                        "papers_per_second": round(len(papers) / max(self.search_stats['search_time'], 1), 1)
                    }
                }
            }
        }

    def format_citations(self, papers: List[Dict[str, Any]]) -> List[str]:
        """格式化引用"""
        citations = []
        for i, paper in enumerate(papers, 1):
            authors = paper.get('authors', [])
            if not authors:
                author_str = "佚名"
            elif len(authors) <= 2:
                author_str = ', '.join(authors)
            else:
                author_str = f"{authors[0]}, et al."

            year = paper.get('year') or "N.D."
            citation = f"[{i}] {author_str}. {paper['title'][:80]}...[J/OL]. Google Scholar, {year}. {paper['url']}"
            citations.append(citation)

        return citations

def save_results(result: Dict[str, Any], output_filename: str = None):
    """保存结果到文件"""

    if not output_filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"literature_search_v5_{timestamp}"

    # 保存JSON格式
    json_filename = f"{output_filename}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 生成Markdown报告
    md_filename = f"{output_filename}.md"
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write("# 文献检索报告 v5.0\n\n")
        f.write("## 检索信息\n")

        input_info = result.get('search_metadata', {}).get('input', {})
        f.write(f"- **题目**: {input_info.get('topic', 'N/A')}\n")
        f.write(f"- **关键词**: {input_info.get('keywords', 'N/A')}\n")
        f.write(f"- **检索语句**: {result['search_metadata'].get('query', 'N/A')}\n")
        f.write(f"- **检索引擎**: {result['search_metadata'].get('engine', 'N/A')}\n")
        f.write(f"- **工具版本**: {result['search_metadata'].get('optimization_version', 'N/A')}\n\n")

        papers = result['search_results']['papers']
        f.write(f"## 检索结果\n")
        f.write(f"- **文献总数**: {len(papers)}\n")

        quality_summary = result['search_results'].get('quality_summary', {})
        f.write(f"- **平均评分**: {quality_summary.get('average_score', 0):.1f}/100\n")
        f.write(f"- **搜索耗时**: {quality_summary.get('performance_metrics', {}).get('search_time_seconds', 0)} 秒\n\n")

        f.write("## 文献列表\n\n")
        for i, paper in enumerate(papers, 1):
            f.write(f"### {i}. {paper['title']}\n")
            f.write(f"- **作者**: {', '.join(paper.get('authors', [])) or '佚名'}\n")
            f.write(f"- **年份**: {paper.get('year') or 'N.D.'}\n")
            f.write(f"- **评分**: {paper['enhanced_score']}/100\n")
            f.write(f"- **链接**: {paper['url']}\n")
            if paper.get('abstract'):
                f.write(f"- **摘要**: {paper['abstract'][:200]}...\n")
            f.write("\n")

        f.write("## 统计信息\n\n")
        quality_dist = quality_summary.get('score_distribution', {})
        f.write(f"- **优秀(≥80)**: {quality_dist.get('excellent', 0)} 篇\n")
        f.write(f"- **良好(60-79)**: {quality_dist.get('good', 0)} 篇\n")
        f.write(f"- **一般(40-59)**: {quality_dist.get('fair', 0)} 篇\n")
        f.write(f"- **较差(<40)**: {quality_dist.get('poor', 0)} 篇\n")

    print(f"\n✅ 结果已保存:")
    print(f"   📄 JSON: {json_filename}")
    print(f"   📝 报告: {md_filename}")

    return json_filename, md_filename

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='优化版学术文献检索工具 v5.0')
    parser.add_argument('topic', nargs='?', help='论文题目')
    parser.add_argument('keywords', nargs='?', help='关键词（逗号分隔）')
    parser.add_argument('major', nargs='?', default='', help='专业领域')
    parser.add_argument('direction', nargs='?', default='', help='研究方向')
    parser.add_argument('max_results', nargs='?', type=int, default=0, help='目标结果数（0=无目标）')

    parser.add_argument('--topic', dest='topic_opt', help='论文题目')
    parser.add_argument('--keywords', dest='keywords_opt', help='关键词（逗号分隔）')
    parser.add_argument('--major', dest='major_opt', default='', help='专业领域')
    parser.add_argument('--direction', dest='direction_opt', default='', help='研究方向')
    parser.add_argument('--max', type=int, default=0, dest='max_results_opt', help='目标结果数（0=无目标）')
    parser.add_argument('--output', help='输出文件名前缀')
    parser.add_argument('--serpapi-key', dest='serpapi_key', help='SerpAPI API Key')
    parser.add_argument('--hl', dest='hl', default='', help='语言代码 (en/zh-CN)')
    parser.add_argument('--ca-bundle', dest='ca_bundle', default='', help='CA证书路径')

    # 新增参数
    parser.add_argument('--min-score', type=int, default=60, help='最低质量分数（默认60）')
    parser.add_argument('--max-rounds', type=int, default=3, help='最大搜索轮数（默认3）')
    parser.add_argument('--no-target-rounds', type=int, default=1, help='无目标模式调用次数（默认1）')
    parser.add_argument('--no-related', action='store_true', help='禁用相关搜索功能')
    parser.add_argument('--num-per-call', type=int, default=20, help='每次API调用最大请求数（默认20）')

    args = parser.parse_args()

    # 处理参数
    topic = args.topic_opt or args.topic or ""
    keywords = args.keywords_opt or args.keywords or ""
    major = args.major_opt or args.major
    direction = args.direction_opt or args.direction
    max_results = args.max_results_opt or args.max_results

    if not topic and not keywords:
        print("❌ 错误: 请提供论文题目或搜索关键词")
        print("用法示例:")
        print("  python3 literature_search_optimized.py '机械结构优化' 'ANSYS,有限元分析' --serpapi-key=YOUR_KEY")
        print("  python3 literature_search_optimized.py --topic='机械结构优化' --keywords='ANSYS,有限元分析' --max=10 --serpapi-key=YOUR_KEY")
        sys.exit(1)

    api_key = args.serpapi_key or os.getenv("SERPAPI_KEY") or os.getenv("SERPAPI_API_KEY")
    if not api_key:
        print("❌ 错误: 缺少 SerpAPI KEY")
        print("请通过 --serpapi-key 或环境变量 SERPAPI_KEY 设置")
        sys.exit(1)

    # 执行搜索
    search_tool = OptimizedLiteratureSearch(
        api_key,
        hl=args.hl,
        ca_bundle=args.ca_bundle,
        num_per_call=args.num_per_call,
        min_quality_score=args.min_score,
        max_rounds=args.max_rounds,
        no_target_mode_rounds=args.no_target_rounds,
        use_related_searches=not args.no_related
    )

    result = search_tool.search_literature(
        topic, keywords, major, direction, max_results
    )

    # 保存结果
    if result.get('search_results', {}).get('papers'):
        save_results(result, args.output)

if __name__ == "__main__":
    main()
