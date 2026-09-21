# Eval Report

> What we measured, what we found, and which configuration we now use.
> Method: [evals.md](./evals.md) · Run: `backend/evals/results/latest.json` · 2026-09-21

---

## The short version

| Question | Answer |
|---|---|
| Does the system store the right things? | **Yes, 96.8%** of 62 labelled messages, with 2 known false positives |
| Does it retrieve the right memories? | **Improved a lot** — precision 64% → **77%**, exact match 57% → **65%** |
| Do the conversation scenarios pass? | **9/10** on a real model (7/10 on the mock — that gap is the mock, not the system) |
| **Does the brain improve answers?** | **Yes — better advice 17–4–3**, and it *reduces* invented facts from 6 to 2 |
| Which constants changed? | threshold `0.60 → 0.55`, floor `0.25 → 0.40`, K `6 → 3` |
| Best model | `gemini-3.8-flash` on balance — ranked mid on usefulness but invented nothing |
| Biggest surprise | **Best-of-each constants do not combine.** Two individually-good values together made things worse. |

---

## 1. What we ran

```
62 labelled messages      Tier 1   storing
23 labelled questions     Tier 2   retrieval
10 scripts / 19 turns     Tier 3   conversations
19 configurations         sweep    one constant at a time
4 models, judged pairwise Tier 4   response quality
```

Tiers 1–3 and the sweep are deterministic and run offline in about 20 seconds.
Tier 4 calls real models and took most of the 25-minute run.

---

## 2. Tier 1 — storing

**96.8% accuracy, 2 junk stored, 0 facts missed, 6/6 conflict actions correct.**

Conflict handling went from 5/6 to **6/6** as a side effect of lowering the promotion
threshold: "I am also getting into photography" scored 0.61 and had been failing the old
0.60 bar by a hair. We did not tune for this — it fell out of a change made for a different
reason, which is worth noting because it cuts both ways: constants interact, and a change
justified by one metric can move another.

The two cases it still gets wrong are genuine limits rather than tuning problems.

| Message | Should | Did | Why |
|---|---|---|---|
| "My friend is a Scorpio" | discard | **stored** | The self-reference gate matches on `my`. It cannot tell *my goal* from *my friend*. |
| "I took the metro to work this morning" | discard | **stored** | A real, specific, self-referential event. Only `topic_supported` argues against it, and commuting is adjacent to `travel`. |

> **Evidence for the "utility is the only thing doing the rejecting" claim.** Both false
> positives score 1.00 on specificity and ~0.92 on extraction. Nothing but the topic term
> separates them from real facts. That is a thin defence, and it is where the next
> improvement should go.

**The `my friend` case is a design limit, not a threshold.** No value of any constant fixes
it; it needs the gate to distinguish the grammatical subject, which a keyword regex cannot do.

---

## 3. Tier 2 — retrieval

**precision 78.1% · recall 83.3% · exact match 69.6% · correct silence 8/8 · 1.39 memories per turn**

Before tuning it was precision 64.3%, exact match 56.5%, silence 7/8, 1.83 per turn.

### A bug the eval did not catch — but a live session did

While driving five demo users through the API, Priya asked *"What do you remember about my
studies?"* and got nothing back, despite having an MBA stored.

The plural stemmer handled `jobs → job` but not `studies → studie`, so it never matched the
lexicon's `study` and the education topic never fired. Fixing it (`-ies → -y`) moved every
retrieval metric at once:

| | before | after |
|---|---|---|
| precision | 77.4% | **78.1%** |
| recall | 80.0% | **83.3%** |
| exact match | 65.2% | **69.6%** |

> **Worth noting how this was found.** 23 labelled questions did not contain an `-ies`
> plural, so the golden set was blind to it. A handful of realistic conversations surfaced
> it immediately. Labelled sets catch regressions; real usage finds the cases you did not
> think to label. Both are needed, and this row is now in the eval set.

### What was wrong

Every single failure was an **extra** memory, never a missing one — the system retrieved
too much, not too little. And every extra came from the *same topic* as the question:

```
"Will I get a promotion?"      expected: m_goal_pm
                               got:      m_goal_pm, m_evt_interview, m_int_entre
```

**Diagnosis:** with the hashed bag-of-words embedder, every career memory scores
`topic_match = 1.0`, so within a topic they are ordered only by
`confidence × importance × decay`. There is no semantic discrimination inside a topic at
all. Raising the floor and lowering K cut the tail that the embedder cannot rank.

> This is the clearest argument in the whole report for replacing the embedder. The fix
> we applied is a workaround: we are discarding the tail because we cannot rank it.

---

## 4. Tier 3 — conversations

**9/10 scripts on `gemini-3.8-flash`, 7/10 on the mock provider.**

The 2-script gap is entirely the mock extractor. "I live in Delhi" and "I prefer replies in
Hindi" contain no lexicon keywords, so the mock returns no candidates and nothing is stored.
The real extractor handles both.

> **Do not read the mock number as a system score.** It measures the stub. The dashboard
> shows both side by side for exactly this reason.

The one genuine failure:

| Script | Turn | Problem |
|---|---|---|
| `correction` | "Where should I settle down?" | Retrieved nothing. "settle" is not in the `travel` lexicon, so topics came back empty and retrieval fell to the weak embedder alone. |

That is a **lexicon coverage gap**, and it shows the cost of rules-first classification:
when the keywords miss, there is no semantic safety net behind them.

---

## 5. The sweep — how we chose the numbers

19 configurations, one constant at a time. A value wins only if the primary metric improves
**and** the counter-metric does not get worse.

### Promotion threshold — *accuracy vs junk stored*

| value | accuracy | junk | |
|---|---|---|---|
| 0.50 | 93.5% | 4 | too loose |
| **0.55** | **96.8%** | **2** | **best** |
| 0.60 | 95.2% | 2 | was current |
| 0.65 | 91.9% | 2 | starts dropping real facts |
| 0.70 | 88.7% | 2 | too strict |

0.55 gains 1.6 points of accuracy at no cost in junk. Below it, junk doubles.

### Retrieval floor — *exact match vs memories injected*

| value | exact match | injected | |
|---|---|---|---|
| 0.15 | 30.4% | 3.43 | floods the prompt |
| 0.20 | 30.4% | 3.43 | |
| 0.25 | 56.5% | 1.83 | was current |
| 0.30 | 56.5% | 1.83 | |
| **0.40** | **60.9%** | **1.78** | **best** |
| 0.50 | 47.8% | 1.13 | now cutting relevant memories |

The curve has a clear peak. Below 0.25 it collapses — the prompt fills with noise.

### Top K — *exact match vs memories injected*

| value | exact match | injected | |
|---|---|---|---|
| **3** | **60.9%** | **1.39** | **best** |
| 4 | 56.5% | 1.61 | |
| 6 | 56.5% | 1.83 | was current |
| 8 | 56.5% | 1.83 | no change — the floor already binds |

K=8 and K=6 are identical, which tells us the **floor, not K, was the binding constraint**
at the old settings.

### Promotion weights — *accuracy vs junk*

| durability / specificity / utility / extraction | accuracy | junk |
|---|---|---|
| 0.35 / 0.25 / 0.25 / 0.15 (current) | 95.2% | 2 |
| 0.25 / 0.25 / 0.35 / 0.15 | 95.2% | 2 |
| 0.40 / 0.20 / 0.25 / 0.15 | 93.5% | 2 |
| 0.25 / 0.25 / 0.25 / 0.25 (equal) | 96.8% | 2 |

Equal weights looked best **in isolation**. See the next section for why we did not take it.

---

## 6. The most important finding: the best values do not combine

A one-at-a-time sweep tells you each constant's best value *holding the others fixed*.
That is not the same as the best combination. We checked:

| configuration | tier 1 accuracy | junk | tier 2 exact | injected |
|---|---|---|---|---|
| current | 95.2% | 2 | 56.5% | 1.83 |
| threshold 0.55 alone | **96.8%** | 2 | 56.5% | 1.83 |
| equal weights alone | **96.8%** | 2 | 56.5% | 1.83 |
| **threshold 0.55 + equal weights** | **93.5%** | **4** | 56.5% | 1.83 |
| floor 0.40 + K 3 | 95.2% | 2 | **65.2%** | 1.35 |

> **Two changes that each improved accuracy to 96.8% dropped it to 93.5% and doubled the
> junk when applied together.**

The reason: equal weights raise `extraction`'s influence, and a lower threshold lets
marginal candidates through. Each alone is safe; together they compound, and four pieces of
junk clear the bar.

**So we kept the current weights.** This is the single strongest argument in the report for
not trusting a one-at-a-time sweep on its own.

---

## 7. The configuration we now use

```python
PROMOTION_THRESHOLD = 0.55      # was 0.60
RETRIEVAL_FLOOR     = 0.40      # was 0.25
TOP_K               = 3         # was 6
PROMOTION_WEIGHTS   = 0.35 / 0.25 / 0.25 / 0.15   # unchanged, see section 6
```

| metric | before | after | |
|---|---|---|---|
| storing accuracy | 95.2% | **96.8%** | ↑ |
| conflict actions | 5/6 | **6/6** | ↑ |
| junk stored | 2 | 2 | — |
| facts missed | 1 | **0** | ↑ |
| retrieval precision | 64.3% | **77.4%** | ↑ |
| retrieval recall | 90.0% | **80.0%** | ↓ **the cost** |
| exact match | 56.5% | **65.2%** | ↑ |
| correct silence | 7/8 | **8/8** | ↑ |
| memories per turn | 1.83 | **1.35** | ↓ (cheaper prompts) |

### The honest trade-off

**Recall dropped 10 points.** We are now retrieving fewer relevant memories in exchange for
much less noise. That is the right call for this product — an astrology assistant that
confidently cites an unrelated memory reads as broken, while one that omits a second
relevant goal merely reads as less thorough — but it is a judgement, not something the data
decided for us.

This is applied in `constants.py`. One existing test changed: it asserted absolute
contradiction counts against the old floor, and now asserts the *invariant* instead
(low-importance memories sink before high-importance ones), which holds at any floor.

---

## 8. Tier 4 — does the brain actually improve answers?

24 judged pairs (brain on vs brain off, same model, same question) plus 8 control pairs,
across four models. **0 judge errors.**

| | on | off | tie |
|---|---|---|---|
| **better advice** | **17** | 4 | 3 |
| **more personalised** | **16** | 5 | 3 |
| **invented facts about the user** | **2** | **6** | — |

### The strongest result: the brain *reduces* hallucination

Brain-off answers invented three times as many facts about the user as brain-on answers
(6 vs 2). That is the opposite of the obvious worry, and it makes sense: given real
memories, the model has something true to say and does not need to fill the space.

> This is the single most useful thing the eval found. "Does memory make the model make
> things up?" is the natural fear, and the measured answer is that it does the reverse.

### It is not personalization theatre

The trap in §6 of [evals.md](./evals.md) was that brain-on would look more personalised
while being no more useful. It did not happen: **personalised 16–5–3 tracks advice 17–4–3**
almost exactly. Both moved together, so the added context is doing real work.

### Evidence — the same question, one model, both arms

> **Q: "What should I focus on for my career?"** · `gemini-3.8-flash` · known: *switch jobs next year*
>
> **brain on** — "…Since **your goal is to make a job switch next year**, right now isn't
> the time for a s…"
>
> **brain off** — "…as a Leo driven by the Sun, your career thrives when you have
> visibility… move away from routine execution."
>
> Both are competent. Only one knows about the job switch.

### Which model is best — and why we do not trust the ranking

| model | rank points | advice on–off–tie | invented |
|---|---|---|---|
| deepseek-v4.1-flash:cloud | 27 | 4–1–1 | 1 |
| deepseek-v4-flash:cloud | 23 | 2–3–1 | 1 |
| gemini-3.8-flash | 15 | 5–0–1 | 0 |
| gemini-3.7-flash | 15 | **6–0–0** | 0 |

**The ranking is not stable between runs.** In the previous run `deepseek-v4-flash` ranked
first with 26 points; here it is second with 23, and it is the only model where the brain
*hurt* (2–3–1) — a position held by `deepseek-v4.1-flash` in the earlier run. With six
pairs per model, per-model conclusions are noise.

> **What is stable:** the aggregate. Two independent runs gave 18–5–1 and 17–4–3. That is
> the number to quote. Per-model results at n=6 are not.

If forced to choose on this evidence: the **Gemini models invented nothing at all** (0 and 0)
and gained consistently from the brain, while the DeepSeek models ranked higher on raw
usefulness but each invented a fact. For an astrology product where a confidently wrong
statement about the user is the worst failure, that argues for `gemini-3.8-flash`.

### The control check — a caution

Controls (questions with nothing stored, where both arms should be near-identical) came out
**5–3–0**. Balanced-ish, but with no ties at all, where the previous run gave 3–2–3.

> A judge that never says "tie" on genuinely similar answers is manufacturing signal. With
> n=8 this is not conclusive, but it argues for reading the main result as a **direction**
> (the brain helps) rather than a measurement (71%).

### A methodology bug worth recording

The first corrected run reported **12** invented facts for brain-on. That was wrong. The
judge was given the literal token `user_profile` in its known-facts list instead of the
expanded fields, so it counted legitimate use of the user's own name as invention —
*"Both answers invent the user's name ('Rahul')"*. Expanding the block changed the count
from 12 to 2.

**The same class of bug appeared three times** in this tier: no known-facts list at all,
then a list that omitted the profile, then a list containing an unexpanded placeholder.
Each time the visible symptom was a plausible-looking number. The only thing that caught it
was reading the judge's written reasons — which is why the rubric asks for a reason at all.

---

## 9. What we deliberately did not tune

| Constants | Why not |
|---|---|
| cosine band, match thresholds | Calibrated for the hashed bag-of-words embedder. Every number refits the moment a real embedding model goes in, so tuning now is wasted work. |
| half-lives, reinforce rate, contradiction factor | They operate over **months**. Measuring them needs a simulated clock that fast-forwards `last_affirmed`. |

---

## 10. Limits of this report

- **We wrote the labels.** The rules are in `evals/rules.md` so they can be challenged
  directly; but the grader is the author.
- **62 messages and 23 questions.** This supports coarse choices (0.55 vs 0.60), never fine
  ones (0.55 vs 0.57). Differences under ~2 points are noise.
- **One embedder.** Every retrieval number is specific to the hashed bag-of-words embedder
  and will move when it is replaced.
- **Tier 3 real-model runs are not deterministic**, so its 9/10 can vary between runs.
