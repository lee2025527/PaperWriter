#!/usr/bin/env python3
"""
Sort in-paragraph citations to ascending order (e.g. [2][1][3] -> [1][2][3]).

Used after reorder_by_first_appearance. Only modifies body paragraphs; reference list unchanged.
"""

from typing import List, Set

from docx.oxml.ns import qn

from reorder_by_first_appearance import (
    REF_PATTERN,
    _extract_ref_numbers_in_order,
    _find_reference_section_end,
    _find_reference_section_start,
    _iter_run_elements,
    _reference_entries_in_list,
)


def _set_citation_display_values(p, new_values: List[str]) -> None:
    """Set the i-th citation in paragraph to new_values[i]. Handles REF field results and plain [n]."""
    if not new_values:
        return
    idx = [0]

    in_result = False
    for r in _iter_run_elements(p):
        t = r.find(qn("w:t"))
        fld_char = r.find(qn("w:fldChar"))

        if fld_char is not None:
            fld_type = fld_char.get(qn("w:fldCharType"))
            if fld_type == "separate":
                in_result = True
            elif fld_type == "end":
                in_result = False

        if in_result and t is not None and t.text and t.text.strip().isdigit():
            if idx[0] < len(new_values):
                t.text = new_values[idx[0]]
                idx[0] += 1
            continue

        if not in_result and t is not None and t.text and REF_PATTERN.search(t.text):
            matches = list(REF_PATTERN.finditer(t.text))
            if not matches:
                continue
            replacements = []
            for i, m in enumerate(matches):
                if idx[0] + i >= len(new_values):
                    break
                replacements.append((m.start(), m.end(), new_values[idx[0] + i]))
            result = []
            last = 0
            for start, end, val in replacements:
                result.append(t.text[last:start])
                result.append(f"[{val}]")
                last = end
            result.append(t.text[last:])
            t.text = "".join(result)
            idx[0] += len(replacements)


def sort_citations_in_paragraphs(
    input_docx: str,
    output_docx: str,
    ref_heading: str,
    stop_headings: Set[str],
) -> int:
    from docx import Document

    doc = Document(input_docx)
    start_idx = _find_reference_section_start(doc, ref_heading)
    if start_idx < 0:
        raise RuntimeError("Reference heading not found or no entries detected.")
    end_idx = _find_reference_section_end(doc, start_idx, stop_headings)
    ref_entries = _reference_entries_in_list(doc, start_idx, end_idx)
    ref_numbers_set = set(e[0] for e in ref_entries)

    changed_paras = 0
    for i in range(0, start_idx):
        p = doc.paragraphs[i]
        numbers = _extract_ref_numbers_in_order(p, ref_numbers_set)
        if len(numbers) <= 1:
            continue
        sorted_nums = sorted(numbers, key=lambda x: int(x))
        if numbers == sorted_nums:
            continue
        _set_citation_display_values(p, sorted_nums)
        changed_paras += 1

    doc.save(output_docx)
    return changed_paras
