# Reference rendering agreement

The leaderboard's English WER is computed after text normalization, so every
formatting choice the normalizer erases is free: the reference's rendering and
the normalizer's rendering of the same words score identically. This directory
measures, per model, how often a model's *raw* output reproduces the reference's
rendering at exactly those spans. It reads only the prediction manifests already
published in the results bucket — no audio, no inference.

## What a site is

Normalizing a raw reference rewrites parts of it. Aligning the raw tokens
against the normalized words identifies each rewritten span; a span whose raw
and normalized forms differ is a **site**. Spans a normalizer rule spans jointly
(`1 000` to `1000`) are merged into one site, since they have no per-token
alignment.

A model is **eligible** at a site when its own normalized output reproduces the
site's normalized words — it got the words right, so only the rendering is in
question — and it **agrees** when its raw output at that span equals the
reference's raw span exactly. The rate is

```
agreement rate = (sites agreed) / (sites the model was eligible at)
```

Eligibility is decided by the same alignment the metric is defined over: the
site's normalized span must fall inside a block that the reference-to-hypothesis
normalized alignment marks equal.

## Classes

A site is labelled by the rewrite that produced it. The first matching label
wins, so the order below is part of the definition.

| class         | rewrite                        | example (raw → normalized)       | V1  | V2  |
| ------------- | ------------------------------ | -------------------------------- | --- | --- |
| `contraction` | apostrophe form expanded       | `don't` → `do not`               | –   | –   |
| `disfluency`  | filler deleted                 | `Uh` → ∅                         | –   | –   |
| `case`        | capitalization only            | `So` → `so`                      | ✓   | –   |
| `punct`       | punctuation or spacing only    | `yeah,` → `yeah`                 | ✓   | –   |
| `spelling`    | en-GB/en-US map entry          | `colour` → `color`               | ✓   | ✓   |
| `abbrev`      | abbreviated honorific expanded | `mr` → `mister`                  | ✓   | ✓   |
| `acronym`     | pointed initialism flattened   | `U.S.` → `u s`                   | ✓   | ✓   |
| `number`      | digits against number words    | `forty` → `40`, `1 000` → `1000` | ✓   | ✓   |
| `other`       | any other rewrite              | `gonna` → `going to`             | ✓   | –   |

## Which sites count

Two tests decide it.

**Audibility.** A site counts only if the audio does not determine the
rendering. Whether a contraction was spoken contracted, and whether a filler was
uttered at all, are facts about the audio, so `contraction` and `disfluency` are
excluded outright.

**Canonicity.** A site counts only if the reference's rendering was a choice
rather than the only correct form. Two rules follow from it.

*Spelling sense-blocklist.* The en-GB/en-US map contains pairs whose American
form is also an ordinary English word with a different sense; there the
reference's spelling is fixed by meaning. Blocked, keyed on the normalized form
(plural forms likewise):

| pair                       | why blocked                                                                 |
| -------------------------- | --------------------------------------------------------------------------- |
| `cheque` / `check`         | the American form is the ordinary verb, and the idiom "checks and balances" |
| `programme` / `program`    | the software sense is spelled `program` in en-GB as well                    |
| `connexion` / `connection` | `connexion` is archaic rather than a live variant                           |
| `tonne` / `ton`            | "tons of" is an intensifier, not a unit of mass                             |
| `practise` / `practice`    | en-GB spells the noun `practice`; only the verb differs                     |
| `draught` / `draft`        | a draft document is a different word, not a variant spelling                |
| `storey` / `story`         | the narrative sense is spelled `story` in en-GB as well                     |
| `metre` / `meter`          | the measuring-device sense is spelled `meter` in en-GB as well              |
| `philtre` / `filter`       | a philtre is a love potion; the pair is miscategorized                      |
| `biassed` / `biased`       | `biassed` is vanishingly rare in either dialect                             |
| `kerb` / `curb`            | the verb "to curb" is spelled the same in en-GB                             |
| `tyre` / `tire`            | the verb "to tire" is spelled the same in en-GB                             |

*Number pruning.* `oh` and `o` for zero are dropped: how a digit was spoken is
audible, not a way of writing it. Ordinals up to `10th` and bare integers below
`11` are dropped: at those magnitudes spelling the number out is the near-uniform
convention of edited prose, so the reference is following a rule rather than
choosing.

## V1 and V2

**V1** pools every retained class. It is dominated by `case` and `punct`, which
are transcript-wide conventions — whether to capitalize sentence-initially,
whether to punctuate at all — so V1 largely measures whether a model's output
follows the benchmark's house style.

**V2** pools `spelling`, `abbrev`, `acronym` and `number`: per-token choices with
no house-style rule behind them, where two renderings of the same audio are both
correct English.

They are not the same measurement: across the 73 models scored on the two
datasets inspected during development, V1 and V2 correlate weakly (Pearson 0.10
and 0.28; Spearman 0.40 and 0.26), and models near the top of one are routinely
mid-table on the other.

## Interpretation

- **A high rate means the output's formatting tracks this benchmark's published
  transcripts.** It does not identify why, and there are innocent reasons. A
  product aiming at verbatim transcription, or one whose output style happens to
  coincide with a benchmark's conventions, can rate high on that benchmark
  legitimately.
- **The informative read is one model across datasets.** The benchmarks differ in
  register and in transcription convention, while a model's output style is
  largely fixed, so a model that rates high everywhere is telling a different
  story from one that rates high on a single benchmark's conventions.
- **Denominators differ between models and must be reported.** Eligibility
  requires reproducing the site's words, so a weaker model is scored on fewer
  sites. Report `v2_n` alongside `v2_rate`, and read the Wilson interval rather
  than the ordering: adjacent models overlap.
- **This is a rate over formatting choices, not a WER**, and not comparable to
  one.
- **English only.** The construction needs the English normalizer's rewrite
  behaviour, so it applies to the English short-form sets.

## Limitations

- **Classification order.** `classify` returns the first matching label, and
  `punct` is tested before `acronym`. A pointed initialism whose punctuation
  removal alone accounts for the rewrite is therefore labelled `punct` and pooled
  into V1, not V2. On one conversational dataset this affects 813 sites, nearly
  all single-letter initials (`T.` → `t`). The behaviour is left as it is because
  the frozen rates are defined over it; treat the `acronym` column as a lower
  bound on acronym volume.
- **One-armed detection.** Only sites where the reference departs from the
  normalizer's canonical form are visible. A reference already in canonical form
  (`honor`, `US`, `2019`) generates no site, although the model faced the same
  choice there. Recovering that arm by inverting the normalizer's tables was
  implemented and audited by hand, up to 40 sampled sites per class and dataset:
  false-positive rates were 30–91% for spelling, 10–92% for acronyms and 58% for
  numbers, with only expanded honorifics clean (0%, n = 9). The inverse is not a
  function — an American spelling is usually also the only correct spelling for
  the sense used, a bare acronym pronounced as a word admits no pointed form, and
  a four-digit year has several natural spoken forms — so it is not shipped.
  Rates are therefore conditional on the choices the reference itself made.
- **Number-class residual.** After pruning, the class still contains years and
  other multi-digit tokens with more than one natural spoken form, so part of it
  reflects which form was heard rather than how it was written. The per-class
  columns exist so the number contribution can be inspected or set aside.
- **Non-pairs in the spelling map.** The map this repo ships contains a few
  entries that are not en-GB/en-US pairs (`ok` and `'kay` to `okay`, `etcetera`
  to `etc`). Each was arbitrated with the audibility test: `'kay` is clipped
  speech, audibly distinct from `okay`, so it is excluded via
  `BLOCKED_RAW_SPELLINGS`; `ok`/`OK` vs `okay` and `etc` vs `etcetera` are read
  identically, so they are kept as genuine free-variant sites. The kept entries
  are rare (a few dozen references across the two datasets inspected) and
  concentrate in conversational transcripts.

## Reproduce

```bash
pip install -r requirements/requirements_jobs.txt

# Syncs the public results bucket, then scores every English short-form set in it.
python ref_rendering/score_ref_rendering.py --bucket hf-audio/asr_leaderboard_h200

# Re-score an already-downloaded copy, one dataset.
python ref_rendering/score_ref_rendering.py --preds-dir results --datasets voxpopuli_test
```

Both the reference and the hypothesis of each row come from the same manifest, so
no cross-file join is needed and manifests keyed `sample_<i>` are usable.

## Outputs

`ref_rendering_<dataset>.csv` — one row per model, sorted by descending V2:

| column                      | meaning                                                  |
| --------------------------- | -------------------------------------------------------- |
| `model`                     | model id as it appears in the results bucket             |
| `v1_rate`, `v1_n`           | agreement rate over all retained classes, and its denominator |
| `v2_rate`, `v2_n`           | agreement rate over `spelling`, `abbrev`, `acronym`, `number` |
| `v2_lo`, `v2_hi`            | 95% Wilson interval on `v2_rate`                         |
| `<class>_rate`, `<class>_n` | the same rate per class, as a diagnostic                 |

## Auditing the sites

`show_sites.py` prints sampled sites with six words of context either side, the
reference's raw span, what the normalizer makes of it, and each model's raw
output aligned to it:

```bash
python ref_rendering/show_sites.py --preds-dir results --dataset voxpopuli_test \
    --models model-a,model-b --class spelling --limit 20 --seed 7

# Same thing as a page.
python ref_rendering/show_sites.py --preds-dir results --dataset ami_test \
    --limit 30 --seed 7 --html sites_ami.html
```

Models are joined on the reference text, so only clips every selected model
transcribed are shown. Sampling is seeded, so a cited site is reproducible.

## Scoring a new model

Place the model's prediction manifest alongside the others and re-run. Either
layout is read:

```
<preds-dir>/<model>/MODEL_<model>_DATASET_hf-audio-open-asr-leaderboard_<dataset>.jsonl
<preds-dir>/<dataset>/<model>.jsonl
```

The manifest must be the one `normalizer.eval_utils.write_manifest` produces, so
that `text` carries the reference and `pred_text` the hypothesis. Predictions
must not be normalized before being written, since the raw rendering is the
measurement.

## Attribution

Adapted from the reference implementation accompanying "Quantifying Benchmark
Optimization in ASR Models"
([HumeAI/asr-benchmark-optimization](https://github.com/HumeAI/asr-benchmark-optimization),
Apache-2.0). Site extraction, classification and scoring are carried over; the
normalizer is this repo's own.
