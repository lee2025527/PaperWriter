"""共享的 matplotlib 中文字体与后端设置。"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

def setup(dpi: int = 200):
    cand = ["PingFang SC", "Heiti SC", "STHeiti", "SimHei", "Microsoft YaHei", "Songti SC", "STSong"]
    found = None
    for f in fm.fontManager.ttflist:
        if any(c in f.name for c in cand):
            found = f.name
            break
    if not found and os.name != "nt":
        mac_fonts = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
        for p in mac_fonts:
            if os.path.exists(p):
                fm.fontManager.addfont(p)
                prop = fm.FontProperties(fname=p)
                found = prop.get_name()
                break
    if found:
        plt.rcParams["font.sans-serif"] = [found] + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt
