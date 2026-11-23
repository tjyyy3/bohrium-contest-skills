"""Offline evidence locators and arithmetic checks for a methods review."""

import argparse
import bisect
import json
import math
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
import re
from statistics import mean, stdev


def locate(path, quote):
    needle = " ".join(quote.split())
    if not needle:
        raise ValueError("provide a nonempty quotation")
    matches = []
    for page_num, page in enumerate(path.read_text(encoding="utf-8-sig").split("\f"), 1):
        # A token retains its original row even if a quote crosses a line break.
        line_starts = [0] + [m.end() for m in re.finditer("\n", page)]
        words = []
        offsets = []
        rows = []
        cursor = 0
        for token in re.finditer(r"\S+", page):
            words.append(token.group())
            offsets.append(cursor)
            rows.append(bisect.bisect_right(line_starts, token.start()))
            cursor += len(token.group()) + 1
        normalized = " ".join(words)
        start = normalized.find(needle)
        while start >= 0:
            first = bisect.bisect_right(offsets, start) - 1
            last = bisect.bisect_right(offsets, start + len(needle) - 1) - 1
            matches.append(dict(page=page_num, lines=[rows[first], rows[last]]))
            start = normalized.find(needle, start + 1)
    return dict(source=str(path), quote=quote, matches=matches)


def percent(count, total, displayed):
    value = Decimal(displayed)
    if total <= 0 or not 0 <= count <= total:
        raise ValueError("require 0 <= count <= total and positive total")
    if not value.is_finite() or not 0 <= value <= 100:
        raise ValueError("provide a finite displayed percentage in [0, 100]")
    step = Fraction(10) ** value.as_tuple().exponent
    actual = Fraction(100 * count, total)
    compatible = abs(actual - Fraction(value)) <= step / 2
    return dict(count=count, total=total, displayed=displayed,
                exact_percent=str(actual), half_last_place=str(step / 2),
                compatible=compatible)


def paired(differences):
    if len(differences) < 2 or not all(map(math.isfinite, differences)):
        raise ValueError("require at least two finite paired differences")
    n = len(differences)
    delta = mean(differences)
    sd = stdev(differences)
    se = sd / math.sqrt(n)
    result = dict(n=n, mean_difference=delta, sd_difference=sd, se=se, df=n - 1)
    if se == 0:
        result["status"] = "t_undefined_zero_standard_error"
    else:
        result.update(t=delta / se, status="computed")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    anchor = modes.add_parser("locate")
    anchor.add_argument("path", type=Path)
    anchor.add_argument("quote")
    ratio = modes.add_parser("percent")
    ratio.add_argument("count", type=int)
    ratio.add_argument("total", type=int)
    ratio.add_argument("displayed")
    pairs = modes.add_parser("paired")
    pairs.add_argument("differences", type=float, nargs="+")
    args = parser.parse_args()
    try:
        if args.mode == "locate":
            result = locate(args.path, args.quote)
        elif args.mode == "percent":
            result = percent(args.count, args.total, args.displayed)
        else:
            result = paired(args.differences)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    except (OSError, ValueError, OverflowError, InvalidOperation) as error:
        parser.exit(2, f"Input or calculation error: {error}\n")
    return 1 if args.mode == "locate" and not result["matches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
