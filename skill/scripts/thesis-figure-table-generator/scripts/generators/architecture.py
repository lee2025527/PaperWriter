"""架构图生成器：多层框 + 模块列表 + 箭头。优化版：解决文字遮挡与对齐问题。"""
from pathlib import Path
from typing import Dict, Any, Optional

def generate(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle
    from . import _matplotlib_setup
    
    # 提高 DPI 以获得更清晰的文字
    _matplotlib_setup.setup(300)

    opts = item.get("options") or {}
    layers_cfg = opts.get("layers", [])

    # 动态调整画布高度
    height = max(6, len(layers_cfg) * 2.2)
    fig, ax = plt.subplots(figsize=(10, height))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, height)
    ax.axis("off")

    y_pos = height - 1.5
    for layer in layers_cfg:
        title = layer.get("title", "")
        subtitle = layer.get("subtitle", "")
        color = layer.get("color", "#3498DB")
        modules = layer.get("modules", [])
        
        # 层大框
        h = 1.6 # 增加层高度以容纳标题和副标题
        rect = FancyBboxPatch((0.5, y_pos), 9, h, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor="none", alpha=0.15)
        ax.add_patch(rect)
        
        # 绘制层左侧标签 (深色小块)
        label_rect = FancyBboxPatch((0.5, y_pos), 2.2, h, boxstyle="round,pad=0.1",
                                   facecolor=color, edgecolor="none", alpha=0.9)
        ax.add_patch(label_rect)
        
        # 层标题
        ax.text(1.6, y_pos + h*0.65, title, ha="center", va="center", 
                fontsize=13, color="white", weight="bold")
        # 副标题 (英文/小字)
        if subtitle:
            # 自动处理过长的副标题
            display_subtitle = subtitle if len(subtitle) < 35 else subtitle[:32] + "..."
            ax.text(1.6, y_pos + h*0.35, display_subtitle, ha="center", va="center", 
                    fontsize=7, color="white", alpha=0.9)

        # 模块小框 (放置在右侧区域)
        nmod = len(modules)
        if nmod > 0:
            start_x = 3.0
            total_w = 6.2
            mw = min(1.8, (total_w - (nmod-1)*0.2) / nmod) # 限制最大宽度
            gap = (total_w - nmod * mw) / (nmod + 1) if nmod > 1 else 0.5
            
            for j, mod in enumerate(modules):
                mx = start_x + gap + j * (mw + gap)
                my = y_pos + h*0.25
                mh = h * 0.5
                
                r = FancyBboxPatch((mx, my), mw, mh, boxstyle="round,pad=0.05",
                                  facecolor="white", edgecolor=color, linewidth=1, alpha=1)
                ax.add_patch(r)
                
                # 模块文字：根据长度动态调整字号
                text_content = str(mod)
                fs = 9
                if len(text_content) > 6: fs = 8
                if len(text_content) > 8: fs = 7
                
                ax.text(mx + mw/2, my + mh/2, text_content, 
                        ha="center", va="center", fontsize=fs, color="#333", weight="medium")
        
        y_pos -= (h + 0.6) # 增加层间距

    plt.tight_layout()
    fid = item.get("id", "图")
    title = item.get("title", "架构图")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-—（）")
    out_path = output_dir / f"{fid}_{safe_title}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()
    return out_path
