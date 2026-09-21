# Design Rationale

> Why every category, constant and formula in [architecture.md](./architecture.md) is what
> it is — and, just as importantly, which ones are genuinely derived and which are priors
> waiting on evaluation data.

## 0. Four grades of justification

Nothing below is presented as empirical unless it is. Each claim carries one of these tags:

| Tag | Meaning |
|---|---|
| **[DERIVED]** | Follows from the assignment spec or from a structural argument |
| **[STANDARD]** | The *form* is established practice; only the constants are ours |
| **[JUDGEMENT]** | A reasoned choice with a stated argument, but no data behind it |
| **[PRIOR]** | An arbitrary round number chosen to be tuned by eval |

The honest summary: the **structure** is derived, the **shapes of the formulas** are
standard, the **orderings** are judgement, and the **exact numbers** are priors.

---

## 1. Where the memory types come from

### 1.1 Six of them are the assignment's own list **[DERIVED]**

The PDF §3 enumerates what the Shared Brain must hold:

> *User profile · Goals · Preferences · Interests · Important memories · Important life
> areas · Astrology attributes*

The taxonomy is that list, restructured so that each entry is distinguished by *behaviour*
rather than by topic:

| PDF bucket | Becomes | Why |
|---|---|---|
| User profile + Astrology attributes | `IDENTITY` | Both are fixed-at-birth facts. Identical lifecycle, so one type. |
| Preferences | `PREFERENCE` | — |
| Interests | `INTEREST` | — |
| Goals | `GOAL` | — |
| Important memories | `EVENT` | "Memory" is the storage word; the *content* is a dated occurrence. |
| Important life areas | **`:Topic` nodes, not a type** | Career/health/marriage are what a memory is *about*, not a kind of memory. Making them nodes is what gives retrieval its 2-hop path. |
| — | `ATTRIBUTE` (added) | Ongoing circumstances (job, city, marital status) fit no bucket above but are the single most useful thing to personalize on. |
| — | `STATE` (added) | The **reject class.** A classifier with no negative class cannot refuse. |

`STATE` is the load-bearing addition. The assignment's hardest requirement is *"do not
store every message"* — that requires an explicit name for the thing you decline to store.

### 1.2 The structural test for whether a type should exist **[DERIVED]**

> **A type exists only if it changes system behaviour** — different decay, different
> conflict handling, or a different place in the prompt. If two proposed types behave
> identically everywhere, they are one type.

Applying it:

| Pair | Same or different? | Because |
|---|---|---|
| `IDENTITY` vs `ATTRIBUTE` | different | identity never decays; attributes do |
| `PREFERENCE` vs `ATTRIBUTE` | different | preference shapes *how* we answer (system prompt); attribute shapes *what* we answer (context block) |
| `GOAL` vs `INTEREST` | different | goals have a target date and can complete; interests cannot |
| `GOAL` vs `EVENT` | different | future vs past; a goal can be achieved or abandoned, an event only ages |
| `STATE` vs everything | different | never promoted at all |

This is also the test for any *future* type: if someone proposes `HABIT`, it earns a slot
only if it decays or conflicts differently from `ATTRIBUTE`.

---

## 2. Where the half-lives come from

### 2.1 What decay actually models **[JUDGEMENT]**

Not "is this still true" — that breaks immediately on `EVENT`, which stays true forever.
Decay models:

> **P(this fact is still worth putting in a prompt today)**

That single definition covers all cases coherently:

- `IDENTITY` — always worth it → no decay
- `ATTRIBUTE` — worth it while probably still true → decays with real-world churn
- `EVENT` — permanently true, but *relevance* fades → decays on interest, not truth

### 2.2 The exponential form **[STANDARD]**

`weight = 0.5 ^ (age / half_life)` is used because it has three properties we need and
almost nothing else does: it is **monotonic**, it **never reaches zero** (so a memory can
always be revived by reaffirmation), and it is **fully described by one parameter per
type** — which keeps the tunable knobs at 7 rather than 7×n.

#### Precedent — and two things it is *not*

The idea that retrieval strength should combine **recency, frequency and contextual
relevance** is not ours; it is the standard account of declarative memory retrieval in the
ACT-R cognitive architecture. ACT-R scores each memory chunk by an activation:

```
A_i = B_i + Σ_j W_j · S_ji            ← base level + spreading activation from context
B_i = ln( Σ_j t_j^(−d) )              ← frequency and recency, d defaults to 0.5
```

Read against our §4 formula: `B_i` is our `confidence × decay` (evidence accumulated,
discounted by time) and `Σ W_j·S_ji` is our `relevance` (activation spreading from what the
user just asked). The **structure** is borrowed. Two honest caveats:

1. **ACT-R decays by a power law (`t^−d`), not an exponential.** We use an exponential
   half-life because it gives one interpretable parameter per type ("how long until this
   class of fact is a coin-flip"), which a power law does not. This is a deliberate
   divergence, not an implementation of ACT-R.
2. **The exponential curve is not Ebbinghaus's original.** Ebbinghaus's own fit was
   logarithmic (`b = 100k / (log t)^c + k`). The exponential `R = e^(−t/S)` form is a later
   simplification from the spaced-repetition lineage, and Wikipedia notes it does not fit
   the original data especially well. We use it for tractability, not fidelity to the 1885 result.

The deeper justification for §2.1's definition of decay — *P(worth putting in a prompt
today)* rather than *P(still true)* — comes from Anderson & Schooler's rational analysis,
which argues memory activation tracks the **environmental need-probability** of a trace:
memory is tuned to estimate the odds an item will be needed *right now*. That is precisely
the quantity we want a retrieval weight to encode.

| Source | What it is |
|---|---|
| [Anderson & Schooler (1991), *Reflections of the Environment in Memory*](https://users.cs.northwestern.edu/~paritosh/papers/KIP/AndersonSchooler1991ReflectionsOfEnvironmentOnMemory.pdf) (free PDF; [journal version](https://journals.sagepub.com/doi/10.1111/j.1467-9280.1991.tb00174.x)) | The need-probability argument — why activation should model "will this be needed", not "is this true" |
| [Schooler & Anderson (2017), *The Adaptive Nature of Memory*](http://act-r.psy.cmu.edu/wordpress/wp-content/uploads/2021/07/SchoolerAnderson2017.pdf) | Accessible book-chapter retelling of the same argument |
| [Brasoveanu, *Intro to the ACT-R subsymbolic level for declarative memory*](https://abrsvn.github.io/files/ACT-R_subsymbolic_3.pdf) | Lecture handout walking through the activation and base-level learning equations |
| [Innerebner, Kowald, Schedl & Lex (2025), *Hybrid Personalization Using Declarative and Procedural Memory Modules of ACT-R*](https://arxiv.org/abs/2505.05083) | Recent work applying ACT-R declarative memory to personalization/recommendation — the same move this design makes |
| [ACT-R project site](http://act-r.psy.cmu.edu/) | Primary documentation and publication list |
| [Forgetting curve](https://en.wikipedia.org/wiki/Forgetting_curve) | Source for the logarithmic-vs-exponential distinction noted above |

### 2.3 The rule that sets each number **[JUDGEMENT]** → **[PRIOR]**

> **half-life ≈ the median real-world duration of that class of fact**

At `t = median duration`, the memory sits at weight 0.5 — still retrievable, no longer
dominant. That is the behaviour we want at exactly the moment a fact becomes a coin-flip.

| Type | Real-world anchor | Half-life |
|---|---|---|
| `IDENTITY` | never changes | ∞ |
| `PREFERENCE` | language/tone preferences shift over years, if ever | 24 mo |
| `ATTRIBUTE` | median job tenure in Indian tech is roughly 1.5–2 yrs | 18 mo |
| `INTEREST` | interests drift on a ~1 yr horizon | 12 mo |
| `GOAL` | most stated goals carry a ≤1 yr horizon; under it, so a goal fades before its deadline rather than after | 9 mo |
| `EVENT` | an event stops being conversationally live after a couple of quarters | 6 mo |

**What is solid:** the *ordering*
`IDENTITY > PREFERENCE > ATTRIBUTE > INTEREST > GOAL > EVENT`.
That ranking is defensible from how fast these things change in a life, and it is what
actually drives behaviour.

**What is not:** the exact months. They are round numbers consistent with the ordering.
Ranking is the design; magnitudes are **[PRIOR]**.

`GOAL` additionally hard-expires at its `target_date` when one is extractable — an explicit
date always beats a statistical default.

---

## 3. Where the promotion formula comes from

```
promotion = 0.35·durability + 0.25·specificity + 0.25·utility + 0.15·extraction_confidence
```

### 3.1 Why exactly these four terms **[DERIVED]**

Enumerate the distinct ways a promotion decision can be wrong. There are four, and they
are independent — a candidate can fail any one while passing the rest:

| Failure | Example shape | Guarded by |
|---|---|---|
| Stored something that stops being true | "I'm busy this week" | **durability** |
| Stored something too vague to ever use | "I want to do better" | **specificity** |
| Stored something true and precise but useless | "I had tea at 4pm" | **utility** |
| Stored something we misread | extractor hallucinated a goal | **extraction_confidence** |

> **One term per independent failure mode.** Four failure modes → four terms.

This is also the admission test for a fifth term: it must catch a failure the existing
four miss. "Recency" fails that test (already in decay). "Sensitivity" fails it (a policy
concern, not a promotion one).

### 3.2 Why a weighted sum, not a product **[DERIVED]**

Because the three hard gates already did the vetoing. Post-gate, the remaining dimensions
should **trade off** — a highly useful, highly specific fact of medium durability should
still get in. A product gives any single mediocre dimension a veto, which post-gate is too
strict. (Retrieval makes the opposite choice, for the opposite reason — see §4.2.)

### 3.3 Why that ordering of weights **[JUDGEMENT]**

Weight by **asymmetric cost of error**:

- **durability (0.35) — highest.** A durability mistake is *actively harmful*: it surfaces
  months later and is wrong, making the product look broken. Every other mistake is merely
  inert clutter. Harm > waste, so durability leads.
- **specificity and utility (0.25 each) — equal.** Both failures produce a memory that is
  useless but harmless. Same cost, so no reason to separate them.
- **extraction_confidence (0.15) — lowest.** Not because it matters least, but because it
  is **partly correlated with the others**: a badly-parsed turn usually also scores low on
  specificity. Weighting it highly would double-count the same evidence.

The ratios (roughly 7:5:5:3) are **[PRIOR]**. The ordering — *durability first,
extraction last, middle two tied* — is the actual design claim, and it is falsifiable by eval.

### 3.4 Why the threshold is 0.60 **[JUDGEMENT]**

Read it back through the weights rather than treating it as a magic number. Extraction
confidence is typically ~0.8, contributing ~0.12. Clearing 0.60 then needs ~0.48 from the
0.85 of remaining weight — an average of ~0.56 across durability, specificity and utility.

> **0.60 means: clearly good on at least two of the three substantive axes, or middling on
> all three.**

That is the intended strictness. The number was chosen to produce that sentence; if eval
shows the system is too eager or too forgetful, this is the first dial to turn.

---

## 4. Where the retrieval score comes from

```
score     = relevance × confidence × importance × decay
relevance = max(topic_match, rescaled_cosine)
```

### 4.1 Why these four factors **[DERIVED]**

Each answers a different question, and no two are correlated:

| Factor | Question | Depends on |
|---|---|---|
| `relevance` | Does this relate to what was just asked? | **the query** |
| `confidence` | Do we believe it? | **evidence history** |
| `importance` | Does this *class* of fact matter for personalization? | **the type** |
| `decay` | Is it still current? | **time** |

Four orthogonal axes: query, belief, prior, time. Drop any one and a specific failure
appears — drop `confidence` and a half-heard guess ranks as high as a stated fact; drop
`importance` and a passing interest outranks a life goal; drop `decay` and the system
quotes last year's job forever.

### 4.2 Why a product, not a sum **[DERIVED]**

These are **conjunctive** — a memory must be relevant AND believed AND important AND
current. The decisive case: if `relevance = 0`, nothing else should rescue it. A sum lets a
high-importance, high-confidence stale memory outscore a perfectly relevant one, which is
precisely the "irrelevant context" failure the assignment grades. A product gives every
factor veto power, which is correct here.

*(Note the deliberate asymmetry with §3.2: promotion sums because gates already vetoed;
retrieval multiplies because relevance itself must be able to veto.)*

### 4.3 Why `max()` for relevance **[JUDGEMENT]**

Two retrieval channels with **complementary blind spots**:

- **topic match** — precise, cheap, deterministic; brittle on paraphrase and unseen vocabulary
- **embedding cosine** — robust to phrasing; fuzzy, and weak on rare exact terms

| Combiner | Semantics | Verdict |
|---|---|---|
| `min` | must satisfy both | too strict — one channel's blind spot kills a good memory |
| weighted sum | average of both | halves the score of a memory one channel nails and the other misses — penalizing it for a *channel's* weakness |
| **`max`** | **either channel suffices** | **correct** — each channel's strength covers the other's gap |

The cost of `max`, stated plainly: a spurious high cosine cannot be vetoed by a topic
mismatch. The floor and the other three multiplicands are the mitigation.

### 4.4 The scale problem with `max` — and the fix **[JUDGEMENT]**

`topic_match` is effectively binary {0, 1}. Raw cosine over real text rarely drops below
~0.5 even for unrelated sentences. A naive `max` is therefore **scale-mismatched**: an
unrelated memory at cosine 0.6 would always beat a topic-missed one at 0.

So cosine is rescaled onto the useful band before comparison:

```
rescaled_cosine = clip((cosine − 0.55) / (0.95 − 0.55), 0, 1)
```

Below ~0.55 contributes nothing; the top of the band maps to 1.0, comparable with a topic
hit. The band edges are **[PRIOR]** and should be re-fitted from the observed cosine
distribution of the actual embedding model — different models have very different
baselines, so hardcoding these without checking is a real trap.

`topic_match` is graded rather than strictly binary: exact topic 1.0, parent topic 0.6.

### 4.5 Why a floor, and why 0.25 **[JUDGEMENT]**

Top-K alone *always* returns K items. On a question unrelated to anything stored, all K are
noise — the exact behaviour the assignment penalizes. The floor makes **"no relevant
context" a reachable outcome**, which is a feature, not a degradation.

0.25 is roughly "a strong topic hit on a mid-confidence memory that has decayed about one
half-life" — the weakest thing still worth a prompt slot. Value is **[PRIOR]**; the
existence of a floor is the design claim.

---

## 5. Where the confidence update comes from

```
reinforce:          confidence ← confidence + 0.15 × (1 − confidence)
weak contradiction: confidence ← confidence × 0.7
```

### 5.1 Why asymptotic, not additive **[DERIVED]**

`+0.15` flat would exceed 1.0 after a few repetitions and needs clamping; worse, it treats
the 5th repetition as strongly as the 1st. Multiplying the *remaining* distance to certainty
gives diminishing returns automatically — 0.60 → 0.66 → 0.71 → 0.75 — which matches how
evidence actually accumulates. It can never exceed 1.0 by construction, so no clamp is needed.

### 5.2 Why contradiction is multiplicative and asymmetric **[JUDGEMENT]**

Downweighting by ×0.7 is **stronger than a single reinforcement** — one contradiction
outweighs one confirmation. That asymmetry is deliberate: a user contradicting themselves
is a much louder signal than a user repeating themselves, because contradiction is
effortful and repetition is often just conversational.

It is also **reversible**, which deletion is not. Two weak contradictions take a memory to
~0.49× and it silently stops clearing the retrieval floor — but if the user reaffirms it,
it climbs back. Wrong guesses decay out instead of destroying data.

### 5.3 Why cardinality decides supersede vs coexist **[DERIVED]**

Superseding on "same type + same topic" is wrong, and this is the highest-risk logic in the
system. *"I want a promotion"* and *"I want to switch careers"* are both `GOAL`+`career` and
both genuinely true — overwriting one with the other destroys real information.

> A new value replaces an old one **only when the slot can hold exactly one value.**

City, language and marital status are single-valued: a person has one. Goals, interests and
events are multi-valued: a person has many. Cardinality is a property of the *slot*, not of
the phrasing, which is why it lives in the type table rather than in the extractor.

---

## 6. What eval is expected to change

Everything tagged **[PRIOR]**, in priority order:

| Rank | Constant | Current | Symptom that it is wrong |
|---|---|---|---|
| 1 | promotion threshold | 0.60 | brain fills with junk / forgets obvious facts |
| 2 | cosine rescale band | 0.55–0.95 | vector channel dominates or never fires |
| 3 | retrieval floor | 0.25 | irrelevant context leaks / context is empty too often |
| 4 | half-life magnitudes | 6–24 mo | stale facts resurface / recent facts vanish |
| 5 | promotion weights | .35/.25/.25/.15 | one failure mode dominates the error set |
| 6 | reinforce α | 0.15 | confidence saturates too fast or never moves |

Items tagged **[DERIVED]** are not tuning targets — if one of those is wrong, the structure
is wrong and the fix is a redesign, not a new number.
