# Labelling rules

Written before the labels, so a disagreement is an argument about a **rule** rather than
about a row. If a row looks wrong, find the rule it came from and change that.

## Set A — should this message become a long-term memory?

**STORE** only if all four hold:

1. **About the user.** The user is the subject. "I want X", "my Y". Not "what does Leo mean".
2. **An assertion, not a request.** No `?`, and it does not open with a request word
   (tell/show/give/explain/what/how/should/can/is/…). "Tell me about my career" is a
   request wearing a statement's clothes.
3. **Has a concrete value.** "I want to do better" has nothing to store. "I want to move
   into product management" does.
4. **Still true and still useful in 30 days.** Moods and one-off events fail this.

**Type** follows the value, not the phrasing:

| Type | Test |
|---|---|
| `IDENTITY` | fixed at birth (dob, birthplace, sun sign) |
| `PREFERENCE` | shapes *how* we should answer (language, tone) |
| `ATTRIBUTE` | an ongoing circumstance (job, city, marital status) |
| `INTEREST` | a durable liking, no target or deadline |
| `GOAL` | a wanted future state, often dated |
| `EVENT` | a dated occurrence, true forever but fading in relevance |
| `STATE` | transient; **never** stored |

**Cardinality decides conflicts, not wording.** One city, one language, one marital status
→ a new value **SUPERSEDES** the old. Many goals, interests, events → a new value
**COEXISTS**.

## Set B — which memories should this question retrieve?

- Label the memories a **thoughtful human assistant would want in front of them** before
  answering. Not everything related — what actually changes the answer.
- `[]` is a valid and important label. If nothing stored bears on the question, the right
  behaviour is to retrieve nothing.
- Follow-ups ("why do you say that") label as `[]`: the conversation window answers them.

## Set C — conversation scripts

Each turn carries an assertion about *behaviour* (was a memory stored, was it retrieved,
was this treated as a follow-up). The final answers are kept for Tier 4 judging.
