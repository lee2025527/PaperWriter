#!/usr/bin/env python3
"""Generate survey/experiment/case/interview data based on a JSON spec.

No external dependencies. Outputs standardized data package under output/work/data/.
"""

import argparse
import csv
import json
import math
import os
import random
import statistics
from datetime import datetime


def load_spec(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def get_std(var):
    if "std" in var and var["std"] is not None:
        return float(var["std"])
    min_v = var.get("min")
    max_v = var.get("max")
    if min_v is not None and max_v is not None:
        return (float(max_v) - float(min_v)) / 6.0
    return 1.0


def generate_numeric(var, mean, rng):
    min_v = float(var.get("min", 0))
    max_v = float(var.get("max", 100))
    distribution = var.get("distribution", "normal")
    std = get_std(var)

    if distribution == "uniform":
        value = rng.uniform(min_v, max_v)
    else:
        value = rng.gauss(mean, std)

    value = clamp(value, min_v, max_v)
    if var.get("type") == "scale":
        value = round(value, 0)
    else:
        value = round(value, 2)
    return value


def generate_categorical(var, rng):
    categories = var.get("categories", [])
    if not categories:
        return ""
    weights = var.get("weights")
    if weights and len(weights) == len(categories):
        return rng.choices(categories, weights=weights, k=1)[0]
    return rng.choice(categories)


def apply_missing(value, missing_rate, rng):
    if missing_rate <= 0:
        return value
    if rng.random() < missing_rate:
        return ""
    return value


def parse_direction_constraints(constraints):
    parsed = []
    for item in constraints:
        item = item.strip()
        if " on " not in item:
            continue
        # Example: "intervention < control on SAS"
        try:
            left, var = item.rsplit(" on ", 1)
            left = left.strip()
            var = var.strip()
            if "<" in left:
                g1, g2 = [x.strip() for x in left.split("<", 1)]
                parsed.append((g1, "<", g2, var))
            elif ">" in left:
                g1, g2 = [x.strip() for x in left.split(">", 1)]
                parsed.append((g1, ">", g2, var))
        except ValueError:
            continue
    return parsed


def prepare_group_means(variables, groups, constraints):
    group_names = [g["name"] for g in groups]
    means = {}
    for var in variables:
        var_name = var["name"]
        means[var_name] = {}
        base_mean = float(var.get("mean", 0))
        var_group_means = var.get("group_means", {})
        for gname in group_names:
            means[var_name][gname] = float(var_group_means.get(gname, base_mean))

    for g1, op, g2, var_name in constraints:
        if var_name not in means:
            continue
        if g1 not in means[var_name] or g2 not in means[var_name]:
            continue
        var = next((v for v in variables if v["name"] == var_name), None)
        if not var:
            continue
        std = get_std(var)
        delta = std * 0.6
        if op == "<":
            means[var_name][g1] = min(means[var_name][g1], means[var_name][g2] - delta)
        elif op == ">":
            means[var_name][g1] = max(means[var_name][g1], means[var_name][g2] + delta)

        min_v = float(var.get("min", -1e9))
        max_v = float(var.get("max", 1e9))
        means[var_name][g1] = clamp(means[var_name][g1], min_v, max_v)
    return means


def generate_rows(sample_size, variables, rng, group_name=None, group_means=None,
                  timepoint=None, missing_rate=0.0):
    rows = []
    for _ in range(sample_size):
        row = {}
        if group_name is not None:
            row["group"] = group_name
        if timepoint is not None:
            row["timepoint"] = timepoint

        for var in variables:
            vname = var["name"]
            vtype = var.get("type", "numeric")
            if vtype in ("numeric", "scale"):
                mean = float(var.get("mean", 0))
                if group_means and vname in group_means and group_name in group_means[vname]:
                    mean = group_means[vname][group_name]
                if timepoint and "timepoint_means" in var:
                    mean = float(var["timepoint_means"].get(timepoint, mean))
                value = generate_numeric(var, mean, rng)
            elif vtype == "categorical":
                value = generate_categorical(var, rng)
            else:
                value = ""
            value = apply_missing(value, missing_rate, rng)
            row[vname] = value
        rows.append(row)
    return rows


def compute_numeric_stats(values):
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (values[0], 0.0)
    return (statistics.mean(values), statistics.pstdev(values))


def summarize_data(rows, variables, group_field=None):
    summary = []
    groups = {None: rows}
    if group_field:
        groups = {}
        for row in rows:
            g = row.get(group_field, "")
            groups.setdefault(g, []).append(row)

    for var in variables:
        vname = var["name"]
        vtype = var.get("type", "numeric")
        for gname, items in groups.items():
            if vtype in ("numeric", "scale"):
                values = [float(r[vname]) for r in items if r.get(vname, "") != ""]
                mean, std = compute_numeric_stats(values)
                summary.append({
                    "group": gname if gname is not None else "overall",
                    "variable": vname,
                    "count": len(values),
                    "mean": round(mean, 2),
                    "std": round(std, 2),
                })
            elif vtype == "categorical":
                counts = {}
                for r in items:
                    val = r.get(vname, "")
                    if val == "":
                        continue
                    counts[val] = counts.get(val, 0) + 1
                summary.append({
                    "group": gname if gname is not None else "overall",
                    "variable": vname,
                    "count": sum(counts.values()),
                    "categories": counts,
                })
    return summary


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build_dictionary(variables, group_field=False, timepoint_field=False):
    lines = ["# 数据字典", ""]
    if group_field:
        lines.append("- `group`: 分组标签")
    if timepoint_field:
        lines.append("- `timepoint`: 时间点标签")
    for var in variables:
        parts = [f"- `{var['name']}`: {var.get('type', 'numeric')}"]
        if "min" in var and "max" in var:
            parts.append(f"范围 {var['min']}–{var['max']}")
        if "categories" in var:
            parts.append(f"类别 {', '.join(var['categories'])}")
        lines.append("  " + "，".join(parts) if parts else "")
    return "\n".join(lines) + "\n"


def build_summary_md(summary):
    lines = ["# 数据摘要", ""]
    for item in summary:
        group = item.get("group", "overall")
        vname = item.get("variable")
        if "categories" in item:
            lines.append(f"## {group} - {vname}")
            lines.append("| 类别 | 频次 |")
            lines.append("| --- | --- |")
            for k, v in item["categories"].items():
                lines.append(f"| {k} | {v} |")
            lines.append("")
        else:
            lines.append(f"- {group} - {vname}: n={item['count']}, mean={item['mean']}, std={item['std']}")
    return "\n".join(lines) + "\n"


def build_provenance(spec_path, spec, seed):
    lines = ["# 数据来源说明", ""]
    lines.append(f"- 规格文件：`{spec_path}`")
    lines.append(f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- 随机种子：{seed}")
    lines.append(f"- 数据类型：{spec['data_spec']['type']}")
    lines.append(f"- 允许模拟：{spec['project'].get('data_allowed', False)}")
    lines.append("- 说明：数据为按规格模拟生成，仅用于论文写作与展示。")
    return "\n".join(lines) + "\n"


def generate_survey(spec, out_dir, rng):
    variables = spec["variables"]
    data_spec = spec["data_spec"]
    sample_size = int(data_spec.get("sample_size", 100))
    groups = data_spec.get("groups")
    missing_rate = float(spec.get("constraints", {}).get("missing_rate", 0))

    rows = []
    if groups:
        for g in groups:
            n = int(g["n"])
            rows.extend(generate_rows(n, variables, rng, group_name=g["name"],
                                      missing_rate=missing_rate))
    else:
        rows = generate_rows(sample_size, variables, rng, missing_rate=missing_rate)

    fieldnames = list(rows[0].keys()) if rows else []
    write_csv(os.path.join(out_dir, "raw.csv"), rows, fieldnames)

    clean_rows = impute_missing(rows, variables)
    write_csv(os.path.join(out_dir, "clean.csv"), clean_rows, fieldnames)

    summary = summarize_data(clean_rows, variables, group_field="group" if groups else None)
    write_markdown(os.path.join(out_dir, "data_dictionary.md"),
                   build_dictionary(variables, group_field=bool(groups)))
    write_markdown(os.path.join(out_dir, "data_summary.md"), build_summary_md(summary))
    write_markdown(os.path.join(out_dir, "scale_scoring.md"),
                   "# 量表计分规则\n\n- 若为标准量表，请按题目要求累加或计算总分。\n")


def generate_experiment(spec, out_dir, rng):
    variables = spec["variables"]
    data_spec = spec["data_spec"]
    groups = data_spec.get("groups", [])
    if not groups:
        raise ValueError("experiment 类型必须包含 groups")
    missing_rate = float(spec.get("constraints", {}).get("missing_rate", 0))
    constraints = spec.get("constraints", {}).get("direction", [])
    constraints = parse_direction_constraints(constraints)
    timepoints = data_spec.get("timepoints")

    group_means = prepare_group_means(variables, groups, constraints)

    rows = []
    for g in groups:
        gname = g["name"]
        n = int(g["n"])
        if timepoints:
            per_time = max(1, n // len(timepoints))
            for t in timepoints:
                rows.extend(generate_rows(per_time, variables, rng, group_name=gname,
                                          group_means=group_means, timepoint=t,
                                          missing_rate=missing_rate))
        else:
            rows.extend(generate_rows(n, variables, rng, group_name=gname,
                                      group_means=group_means, missing_rate=missing_rate))

    fieldnames = list(rows[0].keys()) if rows else []
    write_csv(os.path.join(out_dir, "raw.csv"), rows, fieldnames)

    clean_rows = impute_missing(rows, variables)
    write_csv(os.path.join(out_dir, "clean.csv"), clean_rows, fieldnames)

    group_field = "group" if groups else None
    summary = summarize_data(clean_rows, variables, group_field=group_field)
    write_markdown(os.path.join(out_dir, "data_dictionary.md"),
                   build_dictionary(variables, group_field=True, timepoint_field=bool(timepoints)))
    write_markdown(os.path.join(out_dir, "data_summary.md"), build_summary_md(summary))

    group_stats = build_group_stats(summary)
    write_csv(os.path.join(out_dir, "group_stats.csv"), group_stats,
              ["group", "variable", "count", "mean", "std"])


def generate_case(spec, out_dir):
    template = spec.get("case_template", {})
    fields = template.get("fields", [])
    case_count = int(template.get("cases", spec.get("data_spec", {}).get("sample_size", 3)))
    title = spec.get("project", {}).get("title", "")

    rows = []
    lines = ["# 案例资料", ""]
    for i in range(1, case_count + 1):
        case_id = f"案例{i:02d}"
        lines.append(f"## {case_id}")
        for field in fields:
            text = build_case_field_text(field, title, i)
            lines.append(f"- {field}：{text}")
        lines.append("")

        row = {"case_id": case_id}
        for field in fields:
            row[field] = build_case_field_text(field, title, i, short=True)
        rows.append(row)

    write_markdown(os.path.join(out_dir, "case_profiles.md"), "\n".join(lines) + "\n")
    if rows:
        fieldnames = ["case_id"] + fields
        write_csv(os.path.join(out_dir, "raw.csv"), rows, fieldnames)
        write_csv(os.path.join(out_dir, "clean.csv"), rows, fieldnames)

    write_markdown(os.path.join(out_dir, "data_dictionary.md"), build_case_dictionary(fields))
    write_markdown(os.path.join(out_dir, "data_summary.md"),
                   f"# 数据摘要\n\n- 案例数量：{case_count}\n")


def generate_interview(spec, out_dir):
    template = spec.get("interview_template", {})
    themes = template.get("themes", [])
    quotes_per_theme = int(template.get("quotes_per_theme", 2))

    rows = []
    lines = ["# 访谈主题与摘录", ""]
    for theme in themes:
        lines.append(f"## {theme}")
        for i in range(1, quotes_per_theme + 1):
            quote = build_interview_quote(theme, i)
            lines.append(f"- {quote}")
            rows.append({"theme": theme, "quote": quote})
        lines.append("")

    if rows:
        write_csv(os.path.join(out_dir, "raw.csv"), rows, ["theme", "quote"])
        write_csv(os.path.join(out_dir, "clean.csv"), rows, ["theme", "quote"])

    write_markdown(os.path.join(out_dir, "themes.md"), "\n".join(lines) + "\n")
    write_markdown(os.path.join(out_dir, "data_dictionary.md"),
                   "# 数据字典\n\n- `theme`: 主题\n- `quote`: 访谈摘录\n")
    write_markdown(os.path.join(out_dir, "data_summary.md"),
                   f"# 数据摘要\n\n- 主题数量：{len(themes)}\n- 每主题摘录：{quotes_per_theme}\n")


def build_case_field_text(field, title, idx, short=False):
    suffix = f"（与{title}相关）" if title else ""
    if "基本信息" in field:
        text = f"受试者{idx}，成年，病程与就诊背景已记录{suffix}"
    elif "主要症状" in field:
        text = f"症状以反复上腹不适与消化不良表现为主{suffix}"
    elif "心理状态" in field:
        text = f"出现焦虑与紧张倾向，情绪波动与症状体验相关{suffix}"
    elif "护理干预" in field:
        text = f"实施心理支持与健康教育并行的护理措施{suffix}"
    elif "变化" in field or "结果" in field:
        text = f"症状与情绪体验改善，治疗配合度提升{suffix}"
    else:
        text = f"按项目主题记录相关信息{suffix}"
    if short:
        return text.replace("，", " ")
    return text


def build_interview_quote(theme, idx):
    base = {
        "疾病认知": "对疾病有更清晰的理解后，紧张感减轻",
        "情绪体验": "症状反复时容易焦虑，需要有人安抚",
        "护理体验": "护士解释细致，配合度更高",
        "应对方式": "学会了放松训练，情绪更稳定",
    }
    return f"{base.get(theme, '受访者提到与该主题相关的体验')}（摘录{idx}）"


def build_case_dictionary(fields):
    lines = ["# 数据字典", "", "- `case_id`: 案例编号"]
    for f in fields:
        lines.append(f"- `{f}`: 案例字段")
    return "\n".join(lines) + "\n"


def impute_missing(rows, variables):
    filled = [dict(r) for r in rows]
    for var in variables:
        vname = var["name"]
        vtype = var.get("type", "numeric")
        values = [r[vname] for r in rows if r.get(vname, "") != ""]
        fill_value = ""
        if vtype in ("numeric", "scale"):
            nums = [float(v) for v in values] if values else [0.0]
            fill_value = round(statistics.mean(nums), 2)
        elif vtype == "categorical":
            if values:
                fill_value = max(set(values), key=values.count)
        for r in filled:
            if r.get(vname, "") == "":
                r[vname] = fill_value
    return filled


def build_group_stats(summary):
    stats = []
    for item in summary:
        if "categories" in item:
            continue
        stats.append({
            "group": item["group"],
            "variable": item["variable"],
            "count": item["count"],
            "mean": item["mean"],
            "std": item["std"],
        })
    return stats


def validate_spec(spec):
    project = spec.get("project", {})
    if not project.get("data_allowed", False):
        raise ValueError("data_allowed=false，禁止生成模拟数据")

    data_spec = spec.get("data_spec", {})
    data_type = data_spec.get("type")
    if data_type not in ("survey", "experiment", "case", "interview"):
        raise ValueError("data_spec.type 必须为 survey/experiment/case/interview")

    if data_type in ("survey", "experiment") and not spec.get("variables"):
        raise ValueError("survey/experiment 必须提供 variables")

    if data_type == "experiment" and not data_spec.get("groups"):
        raise ValueError("experiment 必须提供 groups")

    return data_type


def generate(spec_path, out_dir, seed):
    spec = load_spec(spec_path)
    data_type = validate_spec(spec)

    rng = random.Random(seed)
    ensure_dir(out_dir)

    if data_type == "survey":
        generate_survey(spec, out_dir, rng)
    elif data_type == "experiment":
        generate_experiment(spec, out_dir, rng)
    elif data_type == "case":
        generate_case(spec, out_dir)
    elif data_type == "interview":
        generate_interview(spec, out_dir)

    write_markdown(os.path.join(out_dir, "provenance.md"),
                   build_provenance(spec_path, spec, seed))


def main():
    parser = argparse.ArgumentParser(description="Data Generator (survey/experiment/case/interview)")
    parser.add_argument("--spec", required=True, help="Path to data_requirements.json")
    parser.add_argument("--out", default="output/work/data", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    generate(args.spec, args.out, args.seed)


if __name__ == "__main__":
    main()
