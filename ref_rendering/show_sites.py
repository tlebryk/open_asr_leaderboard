#!/usr/bin/env python3
# Copyright 2026 The Open ASR Leaderboard contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Adapted from the reference implementation accompanying "Quantifying Benchmark
# Optimization in ASR Models" (https://github.com/HumeAI/asr-benchmark-optimization,
# Apache-2.0).
"""Print the individual sites `score_ref_rendering.py` scores, for inspection.

Each site is shown one by one: the reference span in context, what the normalizer
turns it into, and each model's raw output aligned to it.

Models are joined on the reference text, so only clips every selected model
transcribed are shown; manifests keyed `sample_<i>` are therefore usable too.

Usage:
    python ref_rendering/show_sites.py --preds-dir results --dataset voxpopuli_test
    python ref_rendering/show_sites.py --preds-dir results --dataset ami_test \
        --models model-a,model-b --class spelling --limit 20 --html sites.html
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, REPO_ROOT)

from ref_rendering_utils import REPORTED_CLASSES, score_clip, sites_for  # noqa: E402
from score_ref_rendering import find_manifests, read_manifest  # noqa: E402

CONTEXT_WORDS = 6

CLASS_COLOR = {
    "case": "#8e6cc3",
    "punct": "#7a869a",
    "spelling": "#d35400",
    "abbrev": "#c0392b",
    "acronym": "#c0392b",
    "number": "#2471a3",
    "other": "#7d6608",
}


def load_hypotheses(manifests: dict[str, str], models: list[str]) -> dict[str, dict[str, str]]:
    """Model to (whitespace-collapsed reference -> hypothesis)."""
    out = {}
    for model in models:
        by_ref = {}
        for row in read_manifest(manifests[model]):
            if "text" not in row or "pred_text" not in row:
                continue
            by_ref[" ".join(row["text"].split())] = row["pred_text"]
        out[model] = by_ref
    return out


def collect_sites(hypotheses: dict[str, dict[str, str]], models: list[str], cls: str | None):
    """Every scored site on the clips all selected models transcribed."""
    refs = set.intersection(*(set(hypotheses[m]) for m in models))
    out = []
    for ref in sorted(refs):
        sites, ref_full = sites_for(ref)
        for index, site in enumerate(sites):
            if cls and site[2] != cls:
                continue
            out.append((ref, tuple(sites), tuple(ref_full), index))
    return out


def context(ref: str, raw_lo: int, raw_hi: int) -> tuple[str, str, str]:
    """``(left, span, right)`` with up to CONTEXT_WORDS words either side."""
    toks = ref.split()
    left = " ".join(toks[max(0, raw_lo - CONTEXT_WORDS) : raw_lo])
    right = " ".join(toks[raw_hi + 1 : raw_hi + 1 + CONTEXT_WORDS])
    if raw_lo - CONTEXT_WORDS > 0:
        left = "… " + left
    if raw_hi + 1 + CONTEXT_WORDS < len(toks):
        right = right + " …"
    return left, " ".join(toks[raw_lo : raw_hi + 1]), right


def verdicts(ref: str, sites, ref_full, index: int, hypotheses, models):
    """``(model, hyp_raw_span, verdict)`` per model at one site."""
    rows = []
    for model in models:
        _, eligible, agreed, hyp_raw = score_clip(list(sites), list(ref_full), hypotheses[model][ref])[index]
        if not eligible:
            rows.append((model, "", "not eligible"))
        else:
            rows.append((model, hyp_raw, "agree" if agreed else "own"))
    return rows


def render_text(dataset, models, samples, hypotheses, total) -> str:
    width = max(len(m) for m in models)
    lines = [f"{dataset}: {len(samples)} of {total} sites, {len(models)} models"]
    for n, (ref, sites, ref_full, index) in enumerate(samples, 1):
        raw_span, norm_span, cls, raw_lo, raw_hi = sites[index][:5]
        left, span, right = context(ref, raw_lo, raw_hi)
        lines += [
            "",
            f"[{n}] {cls}",
            f"  context           {left} «{span}» {right}",
            f"  reference span    {raw_span!r}",
            f"  normalizer        {norm_span!r}",
        ]
        for model, hyp_raw, verdict in verdicts(ref, sites, ref_full, index, hypotheses, models):
            shown = repr(hyp_raw) if verdict != "not eligible" else ""
            lines.append(f"    {model:{width}}  {verdict:12} {shown}")
    return "\n".join(lines) + "\n"


CSS = """
body{font:15px/1.55 -apple-system,Segoe UI,sans-serif;margin:24px auto;max-width:1100px;padding:0 16px;color:#1c2833}
h1{font-size:20px} p.lede{color:#424949}
.site{margin:22px 0;padding:12px 14px;border:1px solid #d5dbdb;border-radius:8px}
.cls{font-size:11px;text-transform:uppercase;letter-spacing:.4px;font-weight:600}
.ctx{color:#566573}
.ctx mark{background:none;border-bottom:2px solid;padding:0 1px;font-weight:600;color:#1c2833}
table{border-collapse:collapse;font-size:13px;margin-top:10px;width:100%}
td,th{border:1px solid #e5e8e8;padding:4px 9px;text-align:left}
th{background:#fbfcfc;font-weight:600}
td.agree{background:#fdedec} td.own{background:#eafaf1} td.na{background:#fbfcfc;color:#b3b6b7}
td.v{white-space:nowrap;font-size:11px;text-transform:uppercase;letter-spacing:.3px}
code{font-size:12px}
.legend span{margin-right:18px;font-size:13px}
.legend .sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-1px;margin-right:4px}
"""


def render_html(dataset, models, samples, hypotheses, total) -> str:
    blocks = [
        f"<h1>Reference-rendering sites — {html.escape(dataset)}</h1>",
        f'<p class="lede">{len(samples)} of {total} scored sites, {len(models)} models. A site is a span of the raw '
        "reference the leaderboard's normalizer rewrites, so both renderings score identically under WER. Where a "
        "model reproduced the site's words, its raw rendering is compared to the reference's.</p>",
        '<p class="legend">'
        '<span><span class="sw" style="background:#fdedec"></span>matched the reference\'s rendering</span>'
        '<span><span class="sw" style="background:#eafaf1"></span>same words, own rendering</span>'
        '<span><span class="sw" style="background:#fbfcfc;border:1px solid #e5e8e8"></span>'
        "not eligible (words not reproduced)</span></p>",
    ]
    for n, (ref, sites, ref_full, index) in enumerate(samples, 1):
        raw_span, norm_span, cls, raw_lo, raw_hi = sites[index][:5]
        left, span, right = context(ref, raw_lo, raw_hi)
        color = CLASS_COLOR.get(cls, "#7a869a")
        rows = []
        for model, hyp_raw, verdict in verdicts(ref, sites, ref_full, index, hypotheses, models):
            klass = {"agree": "agree", "own": "own"}.get(verdict, "na")
            shown = f"<code>{html.escape(hyp_raw)}</code>" if verdict != "not eligible" else "&mdash;"
            label = {"agree": "= reference", "own": "own"}.get(verdict, "not eligible")
            rows.append(
                f'<tr><th>{html.escape(model)}</th><td class="{klass}">{shown}</td>'
                f'<td class="v {klass}">{label}</td></tr>'
            )
        blocks.append(
            f'<div class="site"><span class="cls" style="color:{color}">[{n}] {cls}</span>'
            f'<p class="ctx">{html.escape(left)} <mark style="border-color:{color}">{html.escape(span)}</mark> '
            f"{html.escape(right)}</p>"
            f"<p>reference span <code>{html.escape(raw_span)}</code> &rarr; normalizer "
            f'<code>{html.escape(norm_span) or "&empty;"}</code></p>'
            f'<table><tr><th>model</th><th>raw output at this site</th><th></th></tr>{"".join(rows)}</table></div>'
        )
    return (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>reference-rendering sites — {html.escape(dataset)}</title>"
        f"<style>{CSS}</style>" + "".join(blocks)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--preds-dir", required=True, help="Directory of prediction manifests.")
    parser.add_argument("--dataset", required=True, help="Dataset tag, e.g. voxpopuli_test.")
    parser.add_argument("--models", default=None, help="Comma-separated model ids. Default: every model found.")
    parser.add_argument(
        "--class",
        dest="cls",
        default=None,
        choices=list(REPORTED_CLASSES),
        help="Show only sites of this class. Default: all classes.",
    )
    parser.add_argument("--limit", type=int, default=15, help="Number of sites to sample. Default: 15")
    parser.add_argument("--seed", type=int, default=0, help="Sampling seed. Default: 0")
    parser.add_argument("--html", default=None, help="Write HTML here instead of printing text.")
    args = parser.parse_args()

    manifests = find_manifests(args.preds_dir, args.dataset)
    if not manifests:
        sys.exit(f"No manifests for {args.dataset} under {args.preds_dir}")
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        missing = [m for m in models if m not in manifests]
        if missing:
            sys.exit(f"No {args.dataset} manifest for: {', '.join(missing)}")
    else:
        models = sorted(manifests)

    hypotheses = load_hypotheses(manifests, models)
    sites = collect_sites(hypotheses, models, args.cls)
    if not sites:
        sys.exit("No sites matched.")
    rng = random.Random(args.seed)
    picked = sorted(rng.sample(range(len(sites)), min(args.limit, len(sites))))
    samples = [sites[i] for i in picked]

    if args.html:
        out = render_html(args.dataset, models, samples, hypotheses, len(sites))
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"wrote {args.html} ({len(samples)} of {len(sites)} sites)")
    else:
        sys.stdout.write(render_text(args.dataset, models, samples, hypotheses, len(sites)))


if __name__ == "__main__":
    main()
