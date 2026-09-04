"""流程图生成器：水平/垂直节点 + 箭头。"""
from pathlib import Path
from typing import Dict, Any, Optional

def generate(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    from . import _matplotlib_setup
    _matplotlib_setup.setup(200)

    opts = item.get("options") or {}
    nodes_cfg = opts.get("nodes", [
        {"label": "步骤1", "sublabel": "Step 1", "color": "#4A90E2"},
        {"label": "步骤2", "sublabel": "Step 2", "color": "#50C878"},
    ])
    direction = opts.get("direction", "horizontal")

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")

    n = len(nodes_cfg)
    if direction == "horizontal":
        w = 1.8
        gap = (10 - n * w) / (n + 1) if n else 0.5
        boxes = []
        for i, node in enumerate(nodes_cfg):
            x = gap + i * (w + gap)
            y = 1.1
            label = node.get("label", f"Step{i+1}")
            sublabel = node.get("sublabel", "")
            color = node.get("color", "#4A90E2")
            boxes.append((x, y, w, 0.8, label, sublabel, color))
    else:
        w, h = 2.0, 0.7
        y0 = 2.5
        boxes = []
        for i, node in enumerate(nodes_cfg):
            x = 4
            y = y0 - i * (h + 0.3)
            label = node.get("label", f"Step{i+1}")
            sublabel = node.get("sublabel", "")
            color = node.get("color", "#4A90E2")
            boxes.append((x, y, w, h, label, sublabel, color))

    for i, (x, y, w, h, main_txt, sub_txt, color) in enumerate(boxes):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor="white", linewidth=2, alpha=0.9)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2 + 0.12, main_txt, ha="center", va="center",
                fontsize=13, color="white", weight="bold")
        if sub_txt:
            ax.text(x + w/2, y + h/2 - 0.15, sub_txt, ha="center", va="center",
                    fontsize=9, color="white", alpha=0.9)
        if i < len(boxes) - 1:
            x1, y1 = x + w + 0.05, y + h/2
            x2, y2 = boxes[i+1][0] - 0.05, boxes[i+1][1] + boxes[i+1][3]/2
            arrow = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=25,
                                    linewidth=2.5, color="#34495E", alpha=0.8)
            ax.add_patch(arrow)

    plt.tight_layout()
    fid = item.get("id", "图")
    title = item.get("title", "流程图")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-—（）")
    out_path = output_dir / f"{fid}_{safe_title}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    return out_path
