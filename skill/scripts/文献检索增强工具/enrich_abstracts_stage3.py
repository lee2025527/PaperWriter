#!/usr/bin/env python3
"""
Stage 3 enrichment: only process papers without OpenAlex abstracts.
Attempts layered enrichment with cost controls:
1) Crossref abstract (DOI-based)
2) Unpaywall OA landing page meta
3) Direct HTML meta / PDF (optional)
"""

import argparse
import html
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Phase 1 优化: 新增依赖
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

DOI_REGEX = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


# ============================================================================
# Phase 1 优化: 智能编码检测
# ============================================================================

def smart_decode(raw_bytes: bytes) -> str:
    """
    智能解码字节数据，自动检测编码

    Args:
        raw_bytes: 原始字节数据

    Returns:
        解码后的字符串

    优先级:
        1. chardet 自动检测（置信度≥0.9）
        2. 常见编码尝试（utf-8, gbk, gb2312, big5, iso-8859-1）
        3. 保底方案（utf-8 with errors='replace'）
    """
    if not raw_bytes:
        return ""

    # 策略1: chardet 自动检测
    if HAS_CHARDET:
        try:
            detected = chardet.detect(raw_bytes)
            encoding = detected.get('encoding', 'utf-8')
            confidence = detected.get('confidence', 0)

            # 高置信度直接使用
            if confidence >= 0.9 and encoding:
                try:
                    decoded = raw_bytes.decode(encoding)
                    # 验证：检查是否包含过多替换字符
                    if decoded.count('\ufffd') < 5:
                        return decoded
                except:
                    pass
        except Exception:
            pass

    # 策略2: 尝试常见编码（按中文优先级排序）
    encodings = ['utf-8', 'gbk', 'gb2312', 'big5', 'iso-8859-1', 'latin-1']

    for enc in encodings:
        try:
            decoded = raw_bytes.decode(enc)
            # 简单验证：检查替换字符和乱码模式
            if '\ufffd' not in decoded[:200]:
                # 检查是否包含连续不可打印字符（乱码特征）
                suspicious = sum(1 for c in decoded[:100] if ord(c) > 127 and c not in '，。！？、：""''（）【】《》')
                if suspicious < len(decoded[:100]) * 0.3:  # 乱码字符不超过30%
                    return decoded
        except:
            continue

    # 策略3: 保底方案（使用 replace 替换无法解码的字符）
    return raw_bytes.decode('utf-8', errors='replace')


# ============================================================================
# Phase 1 优化: 改进的 HTML 解析
# ============================================================================

def parse_html_meta_robust(html_text: str) -> str:
    """
    使用 BeautifulSoup 解析 HTML，提取摘要（改进版）

    改进点:
        1. 使用专业HTML解析器（替代正则表达式）
        2. HTML实体自动解码
        3. 更合理的优先级顺序
        4. 更好的错误处理

    Args:
        html_text: HTML文本

    Returns:
        提取的摘要字符串
    """
    if not html_text:
        return ""

    # 如果没有 BeautifulSoup，回退到原方法
    if not HAS_BS4:
        return parse_html_meta(html_text)

    try:
        # 使用 lxml 解析器（更快更准确）
        soup = BeautifulSoup(html_text, 'lxml')
    except:
        try:
            # 回退到 html.parser
            soup = BeautifulSoup(html_text, 'html.parser')
        except:
            return ""

    # 按优先级查找（从最可靠到最通用）
    selectors = [
        # 学术期刊专用 meta 标签
        ('meta[name="citation_abstract"]', 'citation_abstract'),
        ('meta[name="dc.description"]', 'dc.description'),
        ('meta[name="dcterms.abstract"]', 'dcterms.abstract'),
        # Open Graph
        ('meta[property="og:description"]', 'og:description'),
        # 通用描述
        ('meta[name="description"]', 'description'),
        # Twitter Card
        ('meta[name="twitter:description"]', 'twitter:description'),
    ]

    for selector, tag_name in selectors:
        try:
            meta = soup.select_one(selector)
            if meta:
                content = meta.get('content', '').strip()
                if content:
                    # HTML实体解码
                    content = html.unescape(content)
                    # 移除HTML标签（如果有）
                    content = re.sub(r'<[^>]+>', ' ', content)
                    # 清理多余空白
                    content = re.sub(r'\s+', ' ', content).strip()

                    # 验证长度（合理的摘要长度）
                    if len(content) >= 80:
                        return content
        except Exception:
            continue

    return ""


def parse_html_meta(html_text: str) -> str:
    """
    原始HTML解析函数（保留作为回退）
    """
    if not html_text:
        return ""
    metas = {}
    for match in re.finditer(r"<meta\s+[^>]*>", html_text, flags=re.IGNORECASE):
        tag = match.group(0)
        name_match = re.search(r'name=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        prop_match = re.search(r'property=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        content_match = re.search(r'content=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        key = (name_match.group(1) if name_match else prop_match.group(1) if prop_match else "").lower()
        if key and content_match:
            metas[key] = html.unescape(content_match.group(1)).strip()

    for key in META_PRIORITY:
        if key in metas and metas[key]:
            return metas[key]
    return ""


# ============================================================================
# Phase 1 优化: 改进的 PDF 提取
# ============================================================================

def extract_pdf_abstract_robust(pdf_bytes: bytes, max_chars: int = 2000) -> str:
    """
    改进的PDF摘要提取（多策略）

    改进点:
        1. 多策略提取（text, blocks, dict）
        2. 选择最佳结果
        3. 更好的摘要识别模式
        4. 清理和验证

    Args:
        pdf_bytes: PDF文件的字节数据
        max_chars: 最大字符数

    Returns:
        提取的摘要字符串
    """
    if not pdf_bytes:
        return ""

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ""

    # 尝试打开PDF
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return ""

    best_text = ""
    best_length = 0

    # 多策略提取
    strategies = [
        ("text", lambda p: p.get_text("text")),
        ("blocks", lambda p: "\n".join([b[4] for b in p.get_text("blocks") if isinstance(b, (list, tuple)) and len(b) >= 5 and b[4].strip()])),
        ("layout", lambda p: p.get_text("flags=9")),  # 布局感知
    ]

    # 尝试前3页（通常摘要在前几页）
    for page in doc[:3]:
        for strategy_name, strategy_func in strategies:
            try:
                text = strategy_func(page)
                if text and len(text) > best_length:
                    # 简单验证文本质量
                    if len(text.strip()) > 50:
                        best_text = text
                        best_length = len(text)
            except Exception:
                continue

    doc.close()

    if not best_text:
        return ""

    # 清理文本
    best_text = re.sub(r'\s+', ' ', best_text).strip()

    if not best_text:
        return ""

    # 提取摘要（多模式）
    patterns = [
        # 英文摘要（更严格的模式）
        r'(?:Abstract|ABSTRACT)\s*[:\-]?\s*(.{150,3000})\s*(?:Keywords|Introduction|1\.|I\.|\n\n)',
        # 中文摘要
        r'(?:摘要|ABSTRACT)\s*[:\-]?\s*(.{100,2000})\s*(?:关键词|引言|1\.|\n\n)',
        # 简化模式
        r'(?:Abstract|摘要)\s*[:\-]?\s*(.{100,1500})',
    ]

    for pattern in patterns:
        match = re.search(pattern, best_text, re.DOTALL | re.IGNORECASE)
        if match:
            abstract = match.group(1).strip()
            # 截断到合理长度
            if len(abstract) > max_chars:
                abstract = abstract[:max_chars].rstrip()
            # 验证质量
            if len(abstract) >= 80:
                return abstract

    # 如果模式匹配都失败，返回前N个字符（保底）
    if best_length > 200:
        return best_text[:max_chars].rstrip()

    return ""


# ============================================================================
# 保留原有类和函数
# ============================================================================


class RequestBudget:
    def __init__(self, max_requests: int, max_seconds: int) -> None:
        self.max_requests = max_requests
        self.max_seconds = max_seconds
        self.start = time.time()
        self.used = 0

    def allow(self) -> bool:
        if self.used >= self.max_requests:
            return False
        if (time.time() - self.start) >= self.max_seconds:
            return False
        return True

    def consume(self) -> None:
        self.used += 1


def extract_doi(*values: str) -> str:
    for value in values:
        if not value:
            continue
        match = DOI_REGEX.search(value)
        if match:
            doi = match.group(0).strip().rstrip(").,;]>} ")
            return doi
    return ""


# ============================================================================
# Phase 2 优化: 新增数据源
# ============================================================================

def fetch_semantic_scholar(paper: Dict[str, Any], budget: RequestBudget, timeout: int = 20) -> tuple[bool, str]:
    """
    从 Semantic Scholar 获取摘要

    优势:
        - 免费API，无需密钥
        - 覆盖面广（计算机、生物、物理、医学等）
        - 数据质量高（结构化摘要）
        - API限制宽松（100次/5分钟）

    Args:
        paper: 文献信息字典
        budget: 请求预算控制
        timeout: 超时时间

    Returns:
        (成功标志, 摘要文本)
    """
    doi = paper.get('doi') or extract_doi(
        paper.get('url', ''),
        paper.get('publication_summary', ''),
        paper.get('snippet', '')
    )
    title = paper.get('title', '')

    if not doi and not title:
        return False, ""

    # 策略1: 通过 DOI 查询（最准确）
    if doi:
        try:
            encoded_doi = urllib.parse.quote(doi, safe='')
            url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{encoded_doi}"
            params = {"fields": "abstract,title"}

            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            data = request_json(full_url, timeout, "", budget)

            if data and data.get('abstract'):
                abstract = data['abstract'].strip()
                if len(abstract) > 100:
                    return True, abstract
        except Exception as e:
            pass  # 静默失败，继续尝试标题匹配

    # 策略2: 通过标题查询（备用）
    if title:
        try:
            query = urllib.parse.quote(title)
            url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                "query": query,
                "fields": "data.title,data.abstract",
                "limit": 1
            }

            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            data = request_json(full_url, timeout, "", budget)

            if data and data.get('data'):
                papers = data['data']
                if papers and papers[0].get('abstract'):
                    abstract = papers[0]['abstract'].strip()
                    if len(abstract) > 100:
                        return True, abstract
        except Exception:
            pass

    return False, ""


def fetch_europe_pmc(paper: Dict[str, Any], budget: RequestBudget, timeout: int = 20) -> tuple[bool, str]:
    """
    从 Europe PMC 获取摘要

    优势:
        - 生物医学领域强
        - 很多全文 XML
        - 免费 API

    适用场景:
        - 医学、生物学、药学等领域

    Args:
        paper: 文献信息字典
        budget: 请求预算控制
        timeout: 超时时间

    Returns:
        (成功标志, 摘要文本)
    """
    doi = paper.get('doi') or extract_doi(
        paper.get('url', ''),
        paper.get('publication_summary', '')
    )

    if not doi:
        return False, ""

    try:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": f"DOI:{doi}",
            "resulttype": "core",
            "format": "json"
        }

        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        data = request_json(full_url, timeout, "", budget)

        if data:
            results = data.get("resultList", {}).get("result", [])
            if results and results[0].get("abstractText"):
                abstract = results[0]["abstractText"].strip()
                if len(abstract) > 100:
                    return True, abstract
    except Exception:
        pass

    return False, ""


# ============================================================================
# Phase 3 优化: 摘要质量评分系统
# ============================================================================

def score_abstract_quality(abstract: str, source: str = "") -> Dict[str, Any]:
    """
    评估摘要质量

    评分维度:
        1. 长度 (30分): 150-800字为最优
        2. 完整性 (25分): 检查截断和省略号
        3. 结构 (20分): 学术论文典型结构词
        4. 编码 (15分): 检查编码问题
        5. 来源可信度 (10分): 数据源可信度

    Args:
        abstract: 摘要文本
        source: 摘要来源（如 "semantic_scholar"）

    Returns:
        {
            "score": 0-100,
            "quality": "优秀" | "良好" | "一般" | "差",
            "issues": ["问题列表"],
            "completeness": 0-100,
            "length": 实际长度
        }
    """
    score = 0
    issues = []
    length = len(abstract)

    # 1. 长度检查 (30分)
    if length < 100:
        issues.append("过短")
        score += 5
    elif length < 300:
        score += 15
    elif length < 800:
        score += 30  # 最优区间
    elif length < 1500:
        score += 25
    else:
        score += 20  # 过长可能不够精炼

    # 2. 完整性检查 (25分)
    ellipsis_count = abstract.count("...")
    if ellipsis_count == 0:
        score += 25  # 完整
    elif ellipsis_count <= 2:
        issues.append("可能部分截断")
        score += 15
    else:
        issues.append("可能严重截断")
        score += 5

    # 检查截断标记
    truncation_markers = ["[", "等", "etc.", "et al.", "respectively"]
    if any(marker in abstract.lower() for marker in truncation_markers):
        if "可能截断" not in issues:
            issues.append("可能截断")
            score = max(0, score - 5)

    # 3. 结构检查 (20分)
    structure_keywords = [
        # 英文关键词
        'method', 'methods', 'approach', 'algorithm', 'model',
        'result', 'results', 'finding', 'findings',
        'conclusion', 'conclusions',
        'proposed', 'present', 'introduce',
        # 中文关键词
        '方法', '结果', '结论', '实验', '研究',
        '提出', '发现', '表明', '显示'
    ]

    structure_match = sum(1 for kw in structure_keywords if kw.lower() in abstract.lower())
    if structure_match >= 5:
        score += 20
    elif structure_match >= 3:
        score += 15
    elif structure_match >= 1:
        score += 10

    # 4. 编码检查 (15分)
    try:
        abstract.encode('utf-8')
        if '\ufffd' in abstract:  # 替换字符
            issues.append("存在编码问题")
            score += 5
        else:
            score += 15
    except:
        issues.append("编码异常")
        score += 0

    # 5. 来源可信度 (10分)
    source_scores = {
        "semantic_scholar": 10,
        "openalex": 10,
        "crossref": 10,
        "europe_pmc": 10,
        "html_meta": 7,
        "pdf": 8,
        "scholar_snippet": 3,
        "": 5,  # 未知来源
    }
    score += source_scores.get(source.lower(), 5)

    # 质量等级
    if score >= 80:
        quality = "优秀"
    elif score >= 60:
        quality = "良好"
    elif score >= 40:
        quality = "一般"
    else:
        quality = "差"

    # 完整度估算
    if length > 0:
        completeness = min(100, int((length / 800) * 100))
    else:
        completeness = 0

    return {
        "score": score,
        "quality": quality,
        "issues": issues,
        "completeness": completeness,
        "length": length
    }


def update_abstract_with_quality(paper: Dict[str, Any], abstract: str, source: str) -> None:
    """
    更新摘要并计算质量评分（辅助函数）

    Args:
        paper: 文献字典
        abstract: 摘要文本
        source: 数据源
    """
    paper["abstract"] = abstract
    paper["abstract_source"] = source
    # Phase 3: 计算质量评分
    paper["abstract_quality"] = score_abstract_quality(abstract, source)


CONTACT_EMAIL = os.environ.get("OPENALEX_EMAIL", "")
USER_AGENT = "LiteratureEnricher/1.0" + (f" (mailto: {CONTACT_EMAIL})" if CONTACT_EMAIL else "")


def request_json(url: str, timeout: int, ca_bundle: str, budget: RequestBudget) -> Optional[Dict[str, Any]]:
    if not budget.allow():
        return None
    context = ssl.create_default_context(cafile=ca_bundle) if ca_bundle else None
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        budget.consume()
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            print(f"   ⚠️ HTTP 错误 {exc.code}: {url}")
        return None
    except urllib.error.URLError as exc:
        print(f"   ⚠️ 连接失败: {exc.reason}")
        return None


def request_text(url: str, timeout: int, ca_bundle: str, budget: RequestBudget) -> str:
    """HTTP GET 请求，返回文本内容（使用智能编码检测）"""
    if not budget.allow():
        return ""
    context = ssl.create_default_context(cafile=ca_bundle) if ca_bundle else None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        budget.consume()
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            content_type = response.headers.get("Content-Type", "")
            # 只处理文本内容
            if "text" not in content_type and "html" not in content_type and "xml" not in content_type:
                return ""
            # Phase 1 优化: 使用智能解码
            raw_bytes = response.read()
            return smart_decode(raw_bytes)
    except Exception:
        return ""


def request_bytes(url: str, timeout: int, ca_bundle: str, budget: RequestBudget) -> bytes:
    if not budget.allow():
        return b""
    context = ssl.create_default_context(cafile=ca_bundle) if ca_bundle else None
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        budget.consume()
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return response.read()
    except Exception:
        return b""


def strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_crossref_abstract(data: Dict[str, Any]) -> str:
    message = data.get("message") or {}
    abstract = message.get("abstract") or ""
    if not abstract:
        return ""
    return strip_tags(html.unescape(abstract))


def parse_html_meta(html_text: str) -> str:
    if not html_text:
        return ""
    metas = {}
    for match in re.finditer(r"<meta\s+[^>]*>", html_text, flags=re.IGNORECASE):
        tag = match.group(0)
        name_match = re.search(r'name=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        prop_match = re.search(r'property=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        content_match = re.search(r'content=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
        key = (name_match.group(1) if name_match else prop_match.group(1) if prop_match else "").lower()
        if key and content_match:
            metas[key] = html.unescape(content_match.group(1)).strip()

    for key in META_PRIORITY:
        if key in metas and metas[key]:
            return metas[key]
    return ""


def extract_pdf_abstract(pdf_bytes: bytes, max_chars: int) -> str:
    """
    PDF摘要提取（包装函数，使用改进版本）

    保留此函数名以保持向后兼容
    """
    return extract_pdf_abstract_robust(pdf_bytes, max_chars)


def should_replace(existing: str, candidate: str, min_len: int) -> bool:
    if not candidate or len(candidate) < min_len:
        return False
    if not existing:
        return True
    return len(candidate) > len(existing) + 40


def enrich_paper(
    paper: Dict[str, Any],
    email: str,
    ca_bundle: str,
    budget: RequestBudget,
    use_crossref: bool,
    use_unpaywall: bool,
    use_html: bool,
    use_pdf: bool,
    timeout: int,
    min_len: int,
    max_pdf_chars: int,
    sleep_s: float,
) -> Tuple[bool, str]:
    existing = paper.get("abstract", "")
    doi = paper.get("doi") or extract_doi(
        paper.get("url", ""),
        paper.get("publication_summary", ""),
        paper.get("snippet", ""),
    )
    if doi:
        paper["doi"] = doi

    # ======================================================================
    # Phase 2 优化: 新增数据源（最高优先级）
    # ======================================================================

    # 优先级1: Semantic Scholar（免费，数据质量高，覆盖面广）
    try:
        success, abstract = fetch_semantic_scholar(paper, budget, timeout)
        if success and should_replace(existing, abstract, min_len):
            update_abstract_with_quality(paper, abstract, "semantic_scholar")
            return True, "semantic_scholar"
    except Exception as e:
        pass  # 静默失败，继续其他数据源

    # 优先级2: Europe PMC（生物医学领域强，有条件使用）
    # 注意：这里默认启用，如果不想使用可以注释掉
    try:
        success, abstract = fetch_europe_pmc(paper, budget, timeout)
        if success and should_replace(existing, abstract, min_len):
            update_abstract_with_quality(paper, abstract, "europe_pmc")
            return True, "europe_pmc"
    except Exception as e:
        pass  # 静默失败，继续其他数据源

    # ======================================================================
    # 原有数据源（保持不变）
    # ======================================================================

    landing = ""
    pdf_url = ""
    if use_unpaywall and doi:
        url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}"
        if email:
            url += f"?email={urllib.parse.quote(email)}"
        data = request_json(url, timeout, ca_bundle, budget)
        if data:
            best = data.get("best_oa_location") or {}
            landing = best.get("landing_page_url") or best.get("url") or ""
            pdf_url = best.get("pdf_url") or ""
            if landing:
                paper["oa_landing_page_url"] = landing
            if pdf_url:
                paper["oa_pdf_url"] = pdf_url

            if use_pdf and pdf_url:
                pdf_bytes = request_bytes(pdf_url, timeout, ca_bundle, budget)
                abstract = extract_pdf_abstract(pdf_bytes, max_pdf_chars)
                if should_replace(existing, abstract, min_len):
                    update_abstract_with_quality(paper, abstract, "pdf")
                    paper["pdf_source_url"] = pdf_url
                    return True, "pdf"

    if use_crossref and doi:
        url = f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"
        if email:
            url += f"?mailto={urllib.parse.quote(email)}"
        data = request_json(url, timeout, ca_bundle, budget)
        abstract = parse_crossref_abstract(data) if data else ""
        if should_replace(existing, abstract, min_len):
            update_abstract_with_quality(paper, abstract, "crossref")
            paper["crossref_url"] = url
            return True, "crossref"

    if use_html:
        url = landing or paper.get("oa_landing_page_url") or paper.get("url") or ""
        if url:
            html_text = request_text(url, timeout, ca_bundle, budget)
            # Phase 1 优化: 使用改进的HTML解析
            abstract = parse_html_meta_robust(html_text)
            if should_replace(existing, abstract, min_len):
                update_abstract_with_quality(paper, abstract, "html_meta")
                paper["html_source_url"] = url
                return True, "html_meta"

    if use_pdf:
        pdf_url = pdf_url or paper.get("pdf_url") or paper.get("oa_pdf_url") or ""
        if pdf_url:
            pdf_bytes = request_bytes(pdf_url, timeout, ca_bundle, budget)
            abstract = extract_pdf_abstract(pdf_bytes, max_pdf_chars)
            if should_replace(existing, abstract, min_len):
                update_abstract_with_quality(paper, abstract, "pdf")
                paper["pdf_source_url"] = pdf_url
                return True, "pdf"

    if sleep_s:
        time.sleep(sleep_s)
    return False, ""


def write_markdown(output_path: str, result: Dict[str, Any], stats: Dict[str, Any]) -> None:
    papers = result.get("search_results", {}).get("papers", [])
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 第三步摘要增强报告\n\n")
        f.write("## 增强统计\n")
        f.write(f"- **总文献数**: {stats['total']}\n")
        f.write(f"- **待增强数**: {stats['pending']}\n")
        f.write(f"- **成功增强数**: {stats['updated']}\n\n")

        f.write("### 数据源分布\n")
        # Phase 2: 新增数据源
        if stats.get('semantic_scholar', 0) > 0:
            f.write(f"- **Semantic Scholar**: {stats['semantic_scholar']}\n")
        if stats.get('europe_pmc', 0) > 0:
            f.write(f"- **Europe PMC**: {stats['europe_pmc']}\n")
        # 原有数据源
        if stats.get('crossref', 0) > 0:
            f.write(f"- **Crossref**: {stats['crossref']}\n")
        if stats.get('html_meta', 0) > 0:
            f.write(f"- **HTML Meta**: {stats['html_meta']}\n")
        if stats.get('pdf', 0) > 0:
            f.write(f"- **PDF**: {stats['pdf']}\n")
        f.write("\n")

        # Phase 3: 质量评分统计
        quality = stats.get('quality', {})
        if quality.get('avg_score', 0) > 0:
            f.write("### 质量评分分布\n")
            f.write(f"- **平均质量分**: {quality['avg_score']}/100\n")
            f.write(f"- **优秀** (≥80分): {quality['excellent']}\n")
            f.write(f"- **良好** (60-79分): {quality['good']}\n")
            f.write(f"- **一般** (40-59分): {quality['fair']}\n")
            f.write(f"- **差** (<40分): {quality['poor']}\n")
            f.write("\n")

        f.write("## 文献列表\n\n")
        for i, paper in enumerate(papers, 1):
            f.write(f"### {i}. {paper.get('title', 'N/A')}\n")
            f.write(f"- **作者**: {', '.join(paper.get('authors', [])) or '佚名'}\n")
            f.write(f"- **年份**: {paper.get('year') or 'N.D.'}\n")
            f.write(f"- **DOI**: {paper.get('doi') or 'N/A'}\n")
            f.write(f"- **摘要来源**: {paper.get('abstract_source')}\n")

            # Phase 3: 显示质量评分
            quality = paper.get('abstract_quality', {})
            if quality.get('score'):
                score = quality['score']
                quality_level = quality.get('quality', '')
                f.write(f"- **质量评分**: {score}/100 ({quality_level})\n")

            f.write(f"- **链接**: {paper.get('url') or 'N/A'}\n")
            if paper.get("abstract"):
                f.write(f"- **摘要**: {paper.get('abstract')}\n")
            f.write("\n")


def process_file(path: str, output_dir: str, args: argparse.Namespace) -> None:
    with open(path, "r", encoding="utf-8") as f:
        result = json.load(f)

    papers = result.get("search_results", {}).get("papers", [])
    base_name = os.path.splitext(os.path.basename(path))[0]
    output_json = os.path.join(output_dir, f"{base_name}_stage3.json")
    output_md = os.path.join(output_dir, f"{base_name}_stage3.md")

    if not papers:
        print(f"❌ 未找到文献列表: {path}")
        stats = {
            "total": 0, "pending": 0, "updated": 0,
            # Phase 2: 新增数据源统计
            "semantic_scholar": 0, "europe_pmc": 0,
            # 原有数据源
            "crossref": 0, "html_meta": 0, "pdf": 0,
            # Phase 3: 质量评分统计
            "quality": {
                "excellent": 0, "good": 0, "fair": 0, "poor": 0, "avg_score": 0
            }
        }
        result["stage3_enrichment"] = {
            "mailto": args.email,
            "ca_bundle": bool(args.ca_bundle),
            "stats": stats,
            "budget_used": 0,
        }
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        with open(output_md, "w", encoding="utf-8") as f:
            f.write("# 第三步摘要增强报告\n\n")
            f.write("## 提示\n")
            f.write(f"- 原始文件 {os.path.basename(path)} 中未包含任何文献，故无需增强。\n")
        return

    budget = RequestBudget(args.max_requests, args.max_seconds)
    pending = [p for p in papers if p.get("abstract_source") != "openalex"]

    stats = {
        "total": len(papers),
        "pending": len(pending),
        "updated": 0,
        # Phase 2: 新增数据源统计
        "semantic_scholar": 0,
        "europe_pmc": 0,
        # 原有数据源
        "crossref": 0,
        "html_meta": 0,
        "pdf": 0,
        # Phase 3: 质量评分统计
        "quality": {
            "excellent": 0,  # 优秀 (≥80分)
            "good": 0,       # 良好 (60-79分)
            "fair": 0,       # 一般 (40-59分)
            "poor": 0,       # 差 (<40分)
            "avg_score": 0,  # 平均分
        }
    }

    print(f"🔍 处理文件: {os.path.basename(path)}")
    for paper in pending:
        if not budget.allow():
            print("⚠️ 已达到成本限制，停止继续增强。")
            break
        updated, source = enrich_paper(
            paper=paper,
            email=args.email,
            ca_bundle=args.ca_bundle,
            budget=budget,
            use_crossref=args.use_crossref,
            use_unpaywall=args.use_unpaywall,
            use_html=args.use_html,
            use_pdf=args.use_pdf,
            timeout=args.timeout,
            min_len=args.min_length,
            max_pdf_chars=args.max_pdf_chars,
            sleep_s=args.sleep,
        )
        if updated:
            stats["updated"] += 1
            stats[source] += 1

    # Phase 3: 计算质量评分统计
    quality_scores = []
    for paper in papers:
        quality = paper.get("abstract_quality", {})
        score = quality.get("score", 0)
        if score > 0:
            quality_scores.append(score)
            quality_level = quality.get("quality", "")
            if quality_level == "优秀":
                stats["quality"]["excellent"] += 1
            elif quality_level == "良好":
                stats["quality"]["good"] += 1
            elif quality_level == "一般":
                stats["quality"]["fair"] += 1
            elif quality_level == "差":
                stats["quality"]["poor"] += 1

    # 计算平均分
    if quality_scores:
        stats["quality"]["avg_score"] = round(sum(quality_scores) / len(quality_scores), 1)

    result["stage3_enrichment"] = {
        "mailto": args.email,
        "ca_bundle": bool(args.ca_bundle),
        "stats": stats,
        "budget_used": budget.used,
    }

    base_name = os.path.splitext(os.path.basename(path))[0]
    output_json = os.path.join(output_dir, f"{base_name}_stage3.json")
    output_md = os.path.join(output_dir, f"{base_name}_stage3.md")

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    write_markdown(output_md, result, stats)

    print(f"✅ 输出完成: {output_json}")
    print(f"✅ 输出完成: {output_md}")


def main() -> None:
    parser = argparse.ArgumentParser(description="第三步摘要增强工具（仅处理未增强条目）")
    parser.add_argument("inputs", nargs="+", help="OpenAlex 输出 JSON 文件路径")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    parser.add_argument("--email", default=os.getenv("OPENALEX_EMAIL", ""), help="用于 OpenAlex/Crossref/Unpaywall")
    parser.add_argument("--sleep", type=float, default=0.1, help="每次请求后的休眠秒数")
    parser.add_argument("--timeout", type=int, default=20, help="请求超时时间")
    parser.add_argument("--min-length", type=int, default=200, help="摘要最小长度阈值")
    parser.add_argument("--max-pdf-chars", type=int, default=2000, help="PDF 抽取最大字符数")
    parser.add_argument("--max-requests", type=int, default=120, help="最大请求次数")
    parser.add_argument("--max-seconds", type=int, default=120, help="最大耗时秒数")
    parser.add_argument("--no-crossref", action="store_true", help="关闭 Crossref")
    parser.add_argument("--no-unpaywall", action="store_true", help="关闭 Unpaywall")
    parser.add_argument("--no-html", action="store_true", help="关闭 HTML Meta 抽取")
    parser.add_argument("--no-pdf", action="store_true", help="关闭 PDF 抽取")
    args = parser.parse_args()

    args.use_crossref = not args.no_crossref
    args.use_unpaywall = not args.no_unpaywall
    args.use_html = not args.no_html
    args.use_pdf = not args.no_pdf

    args.ca_bundle = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or ""

    for input_path in args.inputs:
        process_file(input_path, args.output_dir, args)


if __name__ == "__main__":
    main()
