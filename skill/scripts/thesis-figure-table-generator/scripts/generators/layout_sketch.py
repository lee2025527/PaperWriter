"""页面布局示意生成器：区域块 + 标签。"""
from pathlib import Path
from typing import Dict, Any, Optional

def generate(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, FancyBboxPatch
    from . import _matplotlib_setup
    _matplotlib_setup.setup(200)

    opts = item.get("options") or {}
    regions = opts.get("regions", [{"name": "主区", "color": "#ECF0F1"}])
    style = opts.get("style", "web_ui")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7)
    ax.axis("off")

    # 简单布局：标题栏 + 侧边栏 + 主区
    if style == "web_ui" and len(regions) >= 3:
        ax.add_patch(Rectangle((0, 5.8), 11, 1.2, facecolor=regions[0].get("color", "#34495E"), edgecolor="#2C3E50"))
        ax.text(5.5, 6.4, "系统标题", ha="center", va="center", fontsize=12, color="white", weight="bold")
        ax.add_patch(Rectangle((0, 0), 2.8, 5.8, facecolor=regions[1].get("color", "#2C3E50"), edgecolor="#1a252f"))
        ax.text(1.4, 4, "侧边栏\n控制面板", ha="center", va="center", fontsize=10, color="white")
        ax.add_patch(Rectangle((2.8, 0), 8.2, 5.8, facecolor=regions[2].get("color", "#FFFFFF"), edgecolor="#bdc3c7"))
        ax.text(6.9, 2.9, "主区\n内容展示", ha="center", va="center", fontsize=11, color="#34495E")
    else:
        for i, reg in enumerate(regions):
            x, y = 1 + (i % 3) * 3.2, 4.5 - (i // 3) * 2.2
            ax.add_patch(Rectangle((x, y), 2.8, 1.8, facecolor=reg.get("color", "#ECF0F1"), edgecolor="#bdc3c7"))
            ax.text(x + 1.4, y + 0.9, reg.get("name", f"区域{i+1}"), ha="center", va="center", fontsize=10)

    plt.tight_layout()
    fid = item.get("id", "图")
    title = item.get("title", "布局示意")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-—（）")
    out_path = output_dir / f"{fid}_{safe_title}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    return out_path
