"""需手动截图的占位：仅产出说明文件，不生成图片。"""
from pathlib import Path
from typing import Dict, Any, Optional

def generate(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    fid = item.get("id", "图")
    title = item.get("title", "截图")
    opts = item.get("options") or {}
    instructions = opts.get("instructions", "请根据正文要求手动截取系统运行界面，保存为对应文件名后放入图表输出目录。")

    out_path = output_dir / f"{fid}_请手动截图说明.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"{fid} {title}\n\n需手动完成：系统运行界面截图。\n\n操作说明：\n{instructions}\n\n请将截图保存为：{fid}_{title}.png\n"
    out_path.write_text(content, encoding="utf-8")
    return out_path  # 返回说明文件路径，主流程可标记为 manual
