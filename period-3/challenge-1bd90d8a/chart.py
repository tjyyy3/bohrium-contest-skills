import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import warnings


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require_keys(obj, required, location, optional=()):
    if not isinstance(obj, dict):
        raise ValueError(f"{location} must be a JSON object")
    missing = set(required) - obj.keys()
    unknown = obj.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(f"{location} has missing keys {sorted(missing)} and unknown keys {sorted(unknown)}")


def main():
    parser = argparse.ArgumentParser(description="Render an editable scientific chart and its source mapping.")
    parser.add_argument("--data", required=True, type=Path, help="long-form UTF-8 CSV")
    parser.add_argument("--spec", required=True, type=Path, help="chart configuration JSON")
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    parser.add_argument("--previous", type=Path, help="previous output directory for a style-only edit")
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise ValueError(f"output directory already exists: {args.out}")

    data_bytes = args.data.read_bytes()
    spec_bytes = args.spec.read_bytes()
    spec = json.loads(spec_bytes)
    require_keys(spec, ("case_id", "title", "caption", "x", "y", "group", "mode", "style", "synthetic"),
                 "spec", ("replicate_field",))
    x_axis, y_axis, group, style = (spec[key] for key in ("x", "y", "group", "style"))
    require_keys(x_axis, ("field", "label", "unit"), "x")
    require_keys(y_axis, ("field", "label", "unit"), "y")
    require_keys(group, ("field", "order"), "group")
    require_keys(style, ("width_mm", "height_mm", "font_family", "font_size", "colors", "markers", "dpi"), "style")

    mode = spec["mode"]
    if mode not in ("raw_scatter", "raw_line", "mean_sd"):
        raise ValueError("mode must be raw_scatter, raw_line, or mean_sd")
    if type(spec["synthetic"]) is not bool:
        raise ValueError("synthetic must be a JSON boolean")
    if mode == "mean_sd" and "replicate_field" not in spec:
        raise ValueError("mean_sd requires replicate_field")
    order = group["order"]
    if not isinstance(order, list) or not order:
        raise ValueError("group.order must be a nonempty array")
    text_values = {
        "case_id": spec["case_id"], "title": spec["title"], "caption": spec["caption"],
        **{f"x.{key}": value for key, value in x_axis.items()},
        **{f"y.{key}": value for key, value in y_axis.items()},
        "group.field": group["field"], "style.font_family": style["font_family"],
        **{f"group.order[{i}]": value for i, value in enumerate(order)},
    }
    fields = {"x": x_axis["field"], "y": y_axis["field"], "group": group["field"]}
    if "replicate_field" in spec:
        fields["replicate"] = text_values["replicate_field"] = spec["replicate_field"]
    for key, value in text_values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a nonempty string")
    if len(order) != len(set(order)):
        raise ValueError("group.order contains a duplicate label")
    for key in ("width_mm", "height_mm", "font_size", "dpi"):
        value = style[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"style.{key} must be a positive finite number")
    if type(style["dpi"]) is not int:
        raise ValueError("style.dpi must be an integer")
    for key in ("colors", "markers"):
        values = style[key]
        if (not isinstance(values, list) or len(values) < len(order)
                or any(not isinstance(value, str) or not value.strip() for value in values)):
            raise ValueError(f"style.{key} requires at least one nonempty string per group")

    reader = csv.reader(io.StringIO(data_bytes.decode("utf-8-sig"), newline=""), strict=True)
    header = next(reader, [])
    if not header or any(not name.strip() for name in header) or len(header) != len(set(header)):
        raise ValueError("CSV requires a nonempty header with unique column names")
    missing = set(fields.values()) - set(header)
    if missing:
        raise ValueError(f"CSV is missing columns {sorted(missing)}")
    by_group = {label: [] for label in order}
    for record, cells in enumerate(reader, start=2):
        if len(cells) != len(header):
            raise ValueError(f"CSV record {record} has {len(cells)} fields, expected {len(header)}")
        values = dict(zip(header, cells))
        source_values = {field: values[field] for field in fields.values()}
        for field, value in source_values.items():
            if not value.strip():
                raise ValueError(f"CSV record {record} is missing a value in {field!r}")
        coordinates = {}
        for axis in ("x", "y"):
            field = fields[axis]
            try:
                coordinates[axis] = float(values[field])
            except ValueError:
                raise ValueError(f"CSV record {record} field {field!r} must be numeric") from None
            if not math.isfinite(coordinates[axis]):
                raise ValueError(f"CSV record {record} field {field!r} must be finite")
        label = values[fields["group"]]
        if label not in by_group:
            raise ValueError(f"CSV record {record} group {label!r} is absent from group.order")
        by_group[label].append({"row": record, "source_values": source_values, **coordinates})
    absent = [label for label, rows in by_group.items() if not rows]
    if absent:
        raise ValueError(f"group.order lists labels absent from the CSV: {absent}")

    calculations = {"schema_version": 1, "method": "sample_sd_n_minus_1" if mode == "mean_sd" else None,
                    "groups": []}
    marks = []
    for label, rows in by_group.items():
        mark_inputs = [("raw_point", [row], {"x": row["x"], "y": row["y"]}) for row in rows]
        if mode == "raw_line":
            ordered = sorted(rows, key=lambda row: row["x"])
            for left, right in zip(ordered, ordered[1:]):
                if left["x"] == right["x"]:
                    raise ValueError(f"raw_line has duplicate x in group {label!r}, records {left['row']} and {right['row']}")
                mark_inputs.append(("line_segment", [left, right], {
                    axis: [left[axis], right[axis]] for axis in ("x", "y")
                }))
        if mode == "mean_sd":
            by_x = {}
            for row in rows:
                by_x.setdefault(row["x"], []).append(row)
            for x, replicate_rows in sorted(by_x.items()):
                replicates = [row["source_values"][fields["replicate"]] for row in replicate_rows]
                if len(replicates) < 2 or len(replicates) != len(set(replicates)):
                    raise ValueError(f"mean_sd needs at least two distinct replicates at group {label!r}, x={x}")
                raw_y = [row["y"] for row in replicate_rows]
                mean, sd = statistics.mean(raw_y), statistics.stdev(raw_y)
                low, high = mean - sd, mean + sd
                if not all(map(math.isfinite, (low, high))):
                    raise ValueError(f"mean_sd endpoints exceed numeric range at group {label!r}, x={x}")
                n = len(raw_y)
                calculations["groups"].append({
                    "group": label, "x": x, "n": n, "mean": mean, "sd": sd,
                    "rows": [row["row"] for row in replicate_rows], "raw_y": raw_y, "replicates": replicates,
                })
                mark_inputs.append(("mean", replicate_rows, {"x": x, "y": mean}))
                mark_inputs.append(("error_bar", replicate_rows, {
                    "x": x, "y": mean, "low": low, "high": high, "sd": sd, "n": n,
                }))
        for kind, source_rows, values in mark_inputs:
            marks.append({
                "id": f"m{len(marks) + 1:04d}", "kind": kind, "group": label, "fields": fields,
                "rows": [row["row"] for row in source_rows],
                "source_values": [row["source_values"] for row in source_rows], "values": values,
            })

    mapping = {
        "schema_version": 1,
        "source": {"path": "data.csv", "sha256": sha256(data_bytes),
                   "record_numbering": "CSV header is record 1. Numbering counts records, including multiline records once."},
        "semantics": {key: value for key, value in spec.items() if key not in ("title", "caption", "style")},
        "marks": marks,
    }
    semantic_sha256 = sha256(json_bytes(mapping))
    mapping["semantic_sha256"] = semantic_sha256
    change = None
    if args.previous:
        previous_data = (args.previous / "data.csv").read_bytes()
        previous_mapping = json.loads((args.previous / "mapping.json").read_bytes())
        previous_spec_bytes = (args.previous / "spec.json").read_bytes()
        previous_spec = json.loads(previous_spec_bytes)
        if sha256(previous_data) != mapping["source"]["sha256"]:
            raise ValueError("style edit changes source data SHA-256")
        allowed_changes = ("title", "caption", "style")
        if (previous_mapping != mapping
                or {key: value for key, value in previous_spec.items() if key not in allowed_changes}
                != mapping["semantics"]):
            raise ValueError("style edit changes semantic mapping")
        change = {
            "schema_version": 1, "previous_spec_sha256": sha256(previous_spec_bytes),
            "spec_sha256": sha256(spec_bytes), "source_sha256": mapping["source"]["sha256"],
            "semantic_sha256": semantic_sha256,
            "changes": {key: {"before": previous_spec[key], "after": spec[key]}
                        for key in allowed_changes if previous_spec[key] != spec[key]},
        }

    import matplotlib as mpl
    mpl.use("Agg")
    from matplotlib import font_manager, ft2font, pyplot as plt
    from matplotlib.colors import to_rgba
    from matplotlib.lines import Line2D
    from matplotlib.markers import MarkerStyle

    family = style["font_family"]
    font = ft2font.FT2Font(font_manager.findfont(font_manager.FontProperties(family=[family]), fallback_to_default=False))
    for color in style["colors"]:
        if to_rgba(color)[3] == 0:
            raise ValueError(f"style.colors contains transparent color {color!r}")
    for marker in style["markers"]:
        if len(MarkerStyle(marker).get_path().vertices) == 0:
            raise ValueError(f"style.markers contains invisible marker {marker!r}")
    x_label, y_label = (f"{axis['label']} ({axis['unit']})" for axis in (x_axis, y_axis))
    uncertainty = "Raw observations. No uncertainty estimate is displayed."
    if mode == "mean_sd":
        sizes = [item["n"] for item in calculations["groups"]]
        sample_size = str(sizes[0]) if min(sizes) == max(sizes) else f"{min(sizes)} to {max(sizes)}"
        uncertainty = f"Error bars show mean ± sample SD. n per group and x = {sample_size}."
    caption = f"{spec['caption']}\n{uncertainty}"
    if spec["synthetic"]:
        caption = f"Synthetic example. {caption}"
    plot_text = [spec["title"], caption, x_label, y_label, *order]
    missing_glyphs = sorted({char for text in plot_text for char in text
                             if char not in "\r\n" and font.get_char_index(ord(char)) == 0})
    if missing_glyphs:
        raise ValueError(f"font {font.family_name!r} lacks glyphs: " +
                         ", ".join(f"U+{ord(char):04X}" for char in missing_glyphs))

    artifacts = {}
    width, height, dpi = style["width_mm"] / 25.4, style["height_mm"] / 25.4, style["dpi"]
    if min(width * dpi, height * dpi) < 1:
        raise ValueError("figure dimensions at style.dpi must yield at least one pixel on each axis")
    group_style = dict(zip(order, zip(style["colors"], style["markers"])))
    with mpl.rc_context({
        "font.family": [family], "font.size": style["font_size"], "svg.fonttype": "none",
        "svg.hashsalt": semantic_sha256, "pdf.fonttype": 42, "text.parse_math": False,
        "axes.spines.top": False, "axes.spines.right": False, "axes.labelcolor": "#20252b",
        "axes.edgecolor": "#58616a", "axes.linewidth": 0.75,
        "xtick.color": "#343a41", "ytick.color": "#343a41",
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.bbox": None, "savefig.transparent": False,
    }), warnings.catch_warnings():
        warnings.filterwarnings("error", message=r"Glyph .* missing from font", category=UserWarning)
        warnings.filterwarnings("error", message=r"constrained_layout not applied.*", category=UserWarning)
        fig, ax = plt.subplots(figsize=(width, height), dpi=dpi, layout="constrained")
        title_size = style["font_size"] * 1.18
        caption_size = style["font_size"] * 0.86
        renderer = fig.canvas.get_renderer()
        wrapped = []
        for source_text, size in ((spec["title"], title_size), (caption, caption_size)):
            prop = font_manager.FontProperties(family=[family], size=size)
            lines = []
            for paragraph in source_text.splitlines():
                line = ""
                for word in paragraph.split():
                    candidate = f"{line} {word}" if line else word
                    if line and renderer.get_text_width_height_descent(candidate, prop, ismath=False)[0] > width * dpi * 0.93:
                        lines.append(line)
                        line = word
                    else:
                        line = candidate
                lines.append(line)
            wrapped.append("\n".join(lines))
        fig.suptitle(wrapped[0], x=0.03, ha="left", fontsize=title_size, color="#20252b")
        fig.supxlabel(wrapped[1], x=0.03, ha="left", fontsize=caption_size, color="#343a41")
        ax.set(xlabel=x_label, ylabel=y_label)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#dce1e5", linewidth=0.55)
        ax.ticklabel_format(useOffset=False, useMathText=False)
        ax.margins(x=0.09, y=0.13)

        for mark in marks:
            color, marker = group_style[mark["group"]]
            kind, values = mark["kind"], mark["values"]
            if kind == "line_segment":
                ax.plot(values["x"], values["y"], color=color, linewidth=1.3, gid=mark["id"], zorder=2)
            elif kind == "error_bar":
                ax.plot([values["x"], values["x"]], [values["low"], values["high"]], color=color,
                        marker="_", markersize=7, linewidth=1.1, gid=mark["id"], zorder=2)
            else:
                replicate = mode == "mean_sd" and kind == "raw_point"
                ax.plot(values["x"], values["y"], linestyle="none", color=color, marker=marker,
                        markerfacecolor="none" if replicate else color, markeredgewidth=0.85,
                        markersize=3.5 if replicate else 6, gid=mark["id"], zorder=4 if replicate else 3)

        legend = [Line2D([], [], color=color, marker=marker, markersize=5, linewidth=1.2,
                         linestyle="-" if mode == "raw_line" else "none", label=label)
                  for label, (color, marker) in group_style.items()]
        ax.legend(handles=legend, loc="lower left", bbox_to_anchor=(0, 1.02),
                  ncols=min(len(order), 3), frameon=False, borderaxespad=0)
        fig.canvas.draw()
        bounds = fig.get_tightbbox(fig.canvas.get_renderer())
        tolerance = 0.5 / dpi
        if (bounds.x0 < -tolerance or bounds.y0 < -tolerance
                or bounds.x1 > width + tolerance or bounds.y1 > height + tolerance):
            raise ValueError("text or artwork extends outside figure; shorten labels, insert line breaks, or enlarge style dimensions")
        fig.set_layout_engine("none")

        point_scale = 72 / dpi
        bbox = ax.get_window_extent()
        transform = ax.transData.get_affine().get_matrix()
        svg_height = height * 72
        render = {
            "width_mm": style["width_mm"], "height_mm": style["height_mm"], "dpi": dpi,
            "png_pixel_size": list(fig.canvas.get_width_height()), "color_space": "RGB",
            "font_family": font.family_name, "font_file": Path(font.fname).name,
            "font_sha256": sha256(Path(font.fname).read_bytes()),
            "svg_plot_bbox_pt": [bbox.x0 * point_scale, svg_height - bbox.y1 * point_scale,
                                 bbox.width * point_scale, bbox.height * point_scale],
            "data_to_svg_pt": {
                "x_scale": float(transform[0, 0] * point_scale), "x_offset": float(transform[0, 2] * point_scale),
                "y_scale": float(-transform[1, 1] * point_scale),
                "y_offset": float(svg_height - transform[1, 2] * point_scale),
            },
            "matplotlib": mpl.__version__,
        }
        for fmt, metadata in {
            "svg": {"Date": None, "Creator": "chart.py"},
            "pdf": {"CreationDate": None, "Creator": "chart.py"},
            "png": {"Software": "chart.py"},
        }.items():
            with io.BytesIO() as buffer:
                fig.savefig(buffer, format=fmt, dpi=dpi, metadata=metadata)
                artifacts[f"chart.{fmt}"] = buffer.getvalue()
        plt.close(fig)

    artifacts.update({
        "data.csv": data_bytes, "spec.json": spec_bytes, "chart.py": Path(__file__).read_bytes(),
        "mapping.json": json_bytes(mapping), "calculations.json": json_bytes(calculations),
        "render.json": json_bytes(render),
    })
    if change is not None:
        artifacts["change.json"] = json_bytes(change)
    artifacts["result.json"] = json_bytes({
        "case_id": spec["case_id"], "status": "rendered_pending_visual_review", "synthetic": spec["synthetic"],
        "uncertainty": uncertainty, "source_sha256": mapping["source"]["sha256"],
        "semantic_sha256": semantic_sha256, "artifacts": [*artifacts, "manifest.json"],
    })
    artifacts["manifest.json"] = json_bytes({
        "schema_version": 1, "algorithm": "sha256", "files": {name: sha256(data) for name, data in artifacts.items()},
    })
    args.out.mkdir(parents=True)
    for name, contents in artifacts.items():
        (args.out / name).write_bytes(contents)
    print(f"Rendered {len(marks)} mapped marks in {args.out}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, csv.Error,
            ImportError, RuntimeError, UserWarning) as error:
        raise SystemExit(f"chart.py: {error}") from None
