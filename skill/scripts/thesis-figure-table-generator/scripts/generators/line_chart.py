"""折线图生成器：从 data_path (Excel/CSV) 或 options 取数。"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd

def _load_data(data_root: Path, data_path: str, opts: Dict) -> tuple:
    full = (data_root / data_path) if not Path(data_path).is_absolute() else Path(data_path)
    if not full.exists():
        print(f"Warning: Data file not found: {full}")
        return None, None
    
    try:
        if full.suffix.lower() == ".csv":
            df = pd.read_csv(full)
        else:
            df = pd.read_excel(full, engine='openpyxl')
    except Exception as e:
        print(f"Error loading data: {e}")
        return None, None

    if df.empty:
        return None, None
    
    x_key = opts.get("x_key", df.columns[0])
    y_key = opts.get("y_key", df.columns[1] if len(df.columns) > 1 else df.columns[0])
    
    labels = df[x_key].astype(str).tolist()
    values = df[y_key].tolist()
    return labels, values

def generate(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from . import _matplotlib_setup
    _matplotlib_setup.setup(300)

    opts = item.get("options") or {}
    data_path = item.get("data_path") or item.get("data_source")
    
    labels, values = None, None
    if data_path and (Path(data_path).suffix in (".xlsx", ".csv") or "/" in data_path or "." in data_path):
        labels, values = _load_data(data_root, data_path, opts)
    
    if labels is None or values is None:
        labels = ["Batch 1", "Batch 2", "Batch 3", "Batch 4"]
        values = [75.0, 78.5, 76.2, 82.1]

    plt.figure(figsize=(8, 5))
    plt.plot(labels, values, color="#4A90E2", marker="o", markersize=6, linewidth=2, label=item.get("title", ""))
    
    # 标数值
    for i, v in enumerate(values):
        plt.text(i, v + 0.5, f"{v:.2f}", ha="center", va="bottom", fontsize=10)

    plt.xlabel(opts.get("x_label", "批次"), fontsize=12)
    plt.ylabel(opts.get("y_label", "成绩"), fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.xticks(rotation=opts.get("rotation", 0))
    
    plt.gca().spines["top"].set_visible(False)
    plt.gca().spines["right"].set_visible(False)
    
    plt.tight_layout()
    
    fid = item.get("id", "图")
    title = item.get("title", "趋势图")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-—（）/")
    out_path = output_dir / f"{fid}_{safe_title}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path
