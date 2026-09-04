#!/usr/bin/env python3
"""PaperWriter 环境自检:依赖 / SERPAPI_KEY / 中文字体。

用法(在用户项目目录执行):
    python3 <skill路径>/scripts/selfcheck.py

退出码:0=全部通过;1=存在必项失败。
"""
import importlib
import json
import os
import sys
import urllib.request

PASS, FAIL, WARN = "✅", "❌", "⚠️ "
problems: list[str] = []


def ok(msg: str) -> None:
    print(f"{PASS} {msg}")


def bad(msg: str, fix: str) -> None:
    print(f"{FAIL} {msg}\n     修复: {fix}")
    problems.append(msg)


def warn(msg: str) -> None:
    print(f"{WARN} {msg}")


def load_dotenv(cwd: str) -> None:
    """极简 .env 加载(不引入第三方依赖)。"""
    path = os.path.join(cwd, ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def main() -> int:
    cwd = os.getcwd()
    load_dotenv(cwd)

    print(f"PaperWriter 环境自检(目录: {cwd})\n" + "-" * 46)

    # 1) Python 版本
    if sys.version_info >= (3, 9):
        ok(f"Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        bad(f"Python {sys.version_info.major}.{sys.version_info.minor}(需 ≥3.9)", "安装 Python 3.9+")

    # 2) 核心依赖
    required = {
        "docx": "python-docx", "matplotlib": "matplotlib", "yaml": "PyYAML",
        "pandas": "pandas", "PIL": "Pillow", "openpyxl": "openpyxl",
        "pdfplumber": "pdfplumber",
    }
    optional = {"chardet": "chardet", "bs4": "beautifulsoup4", "fitz": "PyMuPDF"}
    for module, pkg in required.items():
        try:
            importlib.import_module(module)
            ok(f"依赖 {pkg}")
        except ImportError:
            bad(f"缺少依赖 {pkg}", "pip install -r requirements.txt")
    for module, pkg in optional.items():
        try:
            importlib.import_module(module)
            ok(f"可选依赖 {pkg}(已装)")
        except ImportError:
            warn(f"可选依赖 {pkg} 未装——文献摘要增强会降级(pip install -r requirements.txt 可补齐)")

    # 3) SERPAPI_KEY(必配)
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if not key:
        bad("缺少 SERPAPI_KEY", "复制 .env.example 为 .env,填入 https://serpapi.com 的免费 key")
    else:
        ok("SERPAPI_KEY 已配置")
        try:
            url = f"https://serpapi.com/account.json?api_key={key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                info = json.load(resp)
            total = info.get("total_searches_left", info.get("plan_searches_left"))
            if info.get("account_rate_limit_per_hour") is None and total is None:
                warn("SerpAPI 账号信息返回异常,key 可能无效,首次检索时会再次验证")
            else:
                ok(f"SerpAPI 账号有效,剩余搜索次数约: {total}")
        except Exception as exc:  # 网络问题不阻断
            warn(f"SerpAPI 连通性检查失败({exc});离线环境可忽略,首次检索时会重试")

    # 4) 中文字体(图表渲染)
    try:
        import matplotlib
        from matplotlib import font_manager
        matplotlib.use("Agg")
        cjk_keywords = ("cjk", "pingfang", "hei", "song", "kai", "ming", "yahei", "wqy", "noto sans sc")
        fonts = {f.name.lower() for f in font_manager.fontManager.ttflist}
        hit = [f for f in fonts if any(k in f for k in cjk_keywords)]
        if hit:
            ok(f"中文字体可用(如 {sorted(hit)[:3]})")
        else:
            bad("未检测到中文字体(图表会乱码)", "macOS 自带 PingFang;Linux 安装 fonts-noto-cjk;Windows 自带微软雅黑")
    except Exception as exc:
        warn(f"字体检查跳过({exc})")

    print("-" * 46)
    if problems:
        print(f"结果: {len(problems)} 项必项未通过。修复后重新运行本脚本。")
        return 1
    print("结果: 全部通过,可以开工。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
