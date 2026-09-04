
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm
import platform

class AcademicEngine:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._setup_fonts()
        self.styles = {
            'primary': '#e3f2fd',   # 柔和蓝 (Soft Blue)
            'secondary': '#f3e5f5', # 柔和紫 (Soft Purple)
            'success': '#e8f5e9',   # 柔和绿 (Soft Green)
            'warning': '#fff9c4',   # 柔和黄 (Soft Yellow)
            'border': '#333333',    # 深灰边框
            'text': '#333333'       # 深灰文字
        }

    def _setup_fonts(self):
        """自动检测操作系统并设置中文字体，确保在 macOS/Linux/Windows 上不乱码"""
        system = platform.system()
        fonts = []
        if system == 'Darwin': # macOS
            fonts = ['PingFang SC', 'Heiti TC', 'Songti SC', 'Arial Unicode MS']
        elif system == 'Windows':
            fonts = ['SimHei', 'Microsoft YaHei', 'SimSun']
        else: # Linux
            fonts = ['Source Han Sans CN', 'WenQuanYi Micro Hei', 'DejaVu Sans']
        
        plt.rcParams['font.sans-serif'] = fonts + plt.rcParams['font.sans-serif']
        plt.rcParams['axes.unicode_minus'] = False

    def draw_diagram(self, name, elements, arrows, figsize=(10, 8)):
        """
        通用框图绘制引擎
        elements: list of (x, y, w, h, text, style_key)
        arrows: list of (x1, y1, x2, y2, label)
        """
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.axis('off')

        for el in elements:
            x, y, w, h, text = el[:5]
            style_key = el[5] if len(el) > 5 else 'primary'
            facecolor = self.styles.get(style_key, self.styles['primary'])
            
            rect = patches.FancyBboxPatch((x, y), w, h, 
                                          boxstyle="round,pad=0.5", 
                                          linewidth=1, 
                                          edgecolor=self.styles['border'], 
                                          facecolor=facecolor)
            ax.add_patch(rect)
            ax.text(x + w/2, y + h/2, text, 
                    ha='center', va='center', fontsize=10, color=self.styles['text'], wrap=True)

        for arr in arrows:
            x1, y1, x2, y2 = arr[:4]
            label = arr[4] if len(arr) > 4 else None
            
            ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                        arrowprops=dict(arrowstyle="->", color=self.styles['border'], lw=1, shrinkA=5, shrinkB=5))
            if label:
                ax.text((x1+x2)/2, (y1+y2)/2 + 1, label, 
                        ha='center', va='bottom', fontsize=8, color=self.styles['text'])

        plt.tight_layout()
        output_path = os.path.join(self.output_dir, f"{name}.png")
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        return output_path

    def draw_placeholder(self, name, description):
        """标准化截图占位符"""
        plt.figure(figsize=(10, 6))
        plt.text(0.5, 0.5, f"[此处插入 {description} 截图]", 
                 ha='center', va='center', fontsize=20, color='gray', fontweight='bold')
        plt.text(0.5, 0.4, "请在开发者工具中打开相应页面并截图替换此占位符", 
                 ha='center', va='center', fontsize=12, color='darkgray')
        plt.axis('off')
        plt.tight_layout()
        output_path = os.path.join(self.output_dir, f"{name}.png")
        plt.savefig(output_path, dpi=300)
        plt.close()
        return output_path
