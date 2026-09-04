"""混淆矩阵图生成器：2x2 或 NxN，支持 options.matrix 或从 data_path 读取。"""
from pathlib import Path
from typing import Dict, Any, Optional

def generate(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from . import _matplotlib_setup
    _matplotlib_setup.setup(200)

    opts = item.get("options") or {}
    labels = opts.get("labels", ["类别A", "类别B"])
    matrix = opts.get("matrix")
    data_path = item.get("data_path")
    if data_path:
        full_path = (data_root / data_path) if not Path(data_path).is_absolute() else Path(data_path)
        if full_path.exists():
            try:
                import csv
                with open(full_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    if len(rows) >= 2 and len(rows[0]) >= 2:
                        matrix = [[float(rows[i][j]) for j in range(len(rows[0]))] for i in range(min(2, len(rows)))]
            except Exception:
                pass
    if matrix is None:
        matrix = [[10, 5], [3, 12]]
    cm = np.array(matrix)

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, cmap="Blues", aspect="equal")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels[:cm.shape[1]], fontsize=12)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels[:cm.shape[0]], fontsize=12)
    ax.set_xlabel("预测类别", fontsize=12)
    ax.set_ylabel("真实类别", fontsize=12)
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(int(cm[i, j])), ha="center", va="center",
                    fontsize=14, color="white" if cm[i, j] > thresh else "black")
    plt.colorbar(im, ax=ax, label="样本数")
    plt.tight_layout()
    fid = item.get("id", "图")
    title = item.get("title", "混淆矩阵")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-—（）")
    out_path = output_dir / f"{fid}_{safe_title}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path
