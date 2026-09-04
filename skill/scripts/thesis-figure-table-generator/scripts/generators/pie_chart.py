"""饼图生成器：从 data_path (Excel/CSV) 或 options 取数。"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd

def _load_data(data_root: Path, data_path: str, opts: Dict) -> tuple:
    full = (data_root / data_path) if not Path(data_path).is_absolute() else Path(data_path)
    if not full.exists():
        return None, None
    try:
        if full.suffix.lower() == ".csv":
            df = pd.read_csv(full)
        else:
            df = pd.read_excel(full, engine='openpyxl')
    except Exception as e:
        return None, None

    x_key = opts.get("x_key", df.columns[0] if not df.empty else "x")
    y_key = opts.get("y_key", df.columns[1] if len(df.columns) > 1 else "y")
    if df.empty: return None, None
    return df[x_key].astype(str).tolist(), df[y_key].tolist()

def generate(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from . import _matplotlib_setup
    _matplotlib_setup.setup(300)

    opts = item.get("options") or {}
    data_path = item.get("data_path") or item.get("data_source")
    labels, values = None, None
    if data_path and (Path(data_path).suffix in (".xlsx", ".csv") or "/" in data_path):
        labels, values = _load_data(data_root, data_path, opts)
    
    if labels is None or values is None:
        labels = ["A", "B", "C", "D"]
        values = [25, 35, 20, 20]

    plt.figure(figsize=(7, 6))
    colors = opts.get("colors", ["#4A90E2", "#5C6BC0", "#26A69A", "#66BB6A", "#FFA726", "#FF7043"])
    plt.pie(values, labels=labels, autopct="%1.1f%%", startangle=140, colors=colors, 
            wedgeprops={"edgecolor": "white", "linewidth": 1.5}, textprops={"fontsize": 11})
    
    # plt.title(item.get("title", ""), fontsize=13, pad=10)
    plt.axis("equal")
    plt.tight_layout()
    
    fid = item.get("id", "图")
    title = item.get("title", "饼图")
    safe_title = "".join(c for c in title if c.isalnum() or c in " _-—（）/")
    out_path = output_dir / f"{fid}_{safe_title}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    return out_path
