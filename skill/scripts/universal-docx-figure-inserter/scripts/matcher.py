import os
import re
from pathlib import Path

class AssetMatcher:
    """智能资产匹配器：负责将占位符 ID 和标题映射到实际文件"""
    def __init__(self, assets_dir):
        self.assets_dir = Path(assets_dir)
        self.files = list(self.assets_dir.iterdir()) if self.assets_dir.exists() else []

    def find_match(self, asset_type, asset_id, title):
        """
        asset_type: '图', '表', '图表'
        asset_id: '4-1', '1.2' 等
        title: 占位符中的标题文字
        """
        if not self.files:
            return None

        # 归一化类型
        t_search = '图' if '图' in asset_type else '表'
        # 兼容英文名
        en_search = 'Figure' if t_search == '图' else 'Table'
        
        # 1. 严格 ID 匹配 (类型+ID)
        # 匹配: 图4-1, 表5-2, Figure4-1...
        for f in self.files:
            name = f.name
            if (name.startswith(t_search) or name.lower().startswith(en_search.lower())) and asset_id in name:
                # 进一步检查 ID 是否是独立的数字单元 (防止 1-1 匹配到 1-11)
                if re.search(rf"{re.escape(asset_id)}(\b|[^0-9])", name):
                    return f

        # 2. 纯 ID 匹配
        # 匹配: 4-1_架构图.png
        for f in self.files:
            if f.name.startswith(asset_id) and (t_search in f.name or en_search.lower() in f.name.lower()):
                return f

        # 3. 模糊标题匹配 (关键词匹配)
        keywords = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,}', title)
        if keywords:
            # 优先匹配包含更多关键词的文件
            matches = []
            for f in self.files:
                score = sum(1 for kw in keywords if kw in f.name)
                if score > 0:
                    # 确保类型符合
                    if t_search in f.name or en_search.lower() in f.name.lower() or (t_search == '图' and f.suffix.lower() in ('.png', '.jpg', '.jpeg')):
                        matches.append((score, f))
            if matches:
                matches.sort(key=lambda x: x[0], reverse=True)
                return matches[0][1]

        return None
