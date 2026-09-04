import copy

def copy_table(source_table, target_paragraph):
    """
    高保真克隆表格：
    通过底层 XML 元素的 deepcopy，将 source_table 中的表格结构（含合并单元格、边框、底纹等）
    完整复制并插入到 target_paragraph 之后。
    """
    # 深度克隆 w:tbl 元素
    tbl_copy = copy.deepcopy(source_table._tbl)
    
    # 注入到目标段落之后
    target_paragraph._p.addnext(tbl_copy)
    return tbl_copy
