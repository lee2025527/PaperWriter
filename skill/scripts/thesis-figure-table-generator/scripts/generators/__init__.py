# 图表类型生成器注册；generate_from_spec 按 item.type 分发到此
from pathlib import Path
from typing import Dict, Any, Optional, Callable

def generate_flowchart(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import flowchart as m
    return m.generate(item, output_dir, data_root)

def generate_architecture(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import architecture as m
    return m.generate(item, output_dir, data_root)

def generate_layout_sketch(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import layout_sketch as m
    return m.generate(item, output_dir, data_root)

def generate_confusion_matrix(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import confusion_matrix as m
    return m.generate(item, output_dir, data_root)

def generate_line_chart(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import line_chart as m
    return m.generate(item, output_dir, data_root)

def generate_bar_chart(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import bar_chart as m
    return m.generate(item, output_dir, data_root)

def generate_pie_chart(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import pie_chart as m
    return m.generate(item, output_dir, data_root)

def generate_table(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import table as m
    return m.generate(item, output_dir, data_root)

def generate_screenshot_placeholder(item: Dict[str, Any], output_dir: Path, data_root: Path) -> Optional[Path]:
    from . import screenshot_placeholder as m
    return m.generate(item, output_dir, data_root)

REGISTRY = {
    "flowchart": generate_flowchart,
    "architecture": generate_architecture,
    "layout_sketch": generate_layout_sketch,
    "confusion_matrix": generate_confusion_matrix,
    "line_chart": generate_line_chart,
    "bar_chart": generate_bar_chart,
    "pie_chart": generate_pie_chart,
    "table": generate_table,
    "screenshot_placeholder": generate_screenshot_placeholder,
}
