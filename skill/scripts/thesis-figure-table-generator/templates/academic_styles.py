import matplotlib.pyplot as plt
import os

def setup_academic_style():
    """
    配置全局学术图表样式，兼容跨平台中文字体。
    """
    fonts = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC', 'SimHei', 'Microsoft YaHei']
    plt.rcParams['font.sans-serif'] = fonts
    plt.rcParams['axes.unicode_minus'] = False
    
    # 统一配色：科技蓝主题
    return {
        'primary_color': '#1f77b4',
        'bg_color': '#e1f5fe',
        'secondary_bg': '#f5f5f5',
        'text_color': '#333333',
        'border_color': '#757575',
        'highlight_color': '#ff9800',
        'warning_color': '#f44336',
        'success_color': '#4caf50'
    }

def save_clean_figure(filename, output_dir='output/deliver/论文图表'):
    """
    以干净的格式保存图表（无边框空白，高DPI）。
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{filename}.png")
    plt.tight_layout()
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ Generated Figure: {filepath}")
