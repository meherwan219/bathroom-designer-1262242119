# Demo walkthrough

Per plan.md's Phase 5: one scripted path — small Indian apartment,
tight budget, eco preference, then "add rain shower" → infeasible →
repair. Run it yourself:

```bash
cd apps/api && python3 demo.py
```

Every number below is copied verbatim from an actual run of that
script, not written by hand. The script is also a permanent test
(`tests/test_demo_script.py`), so this walkthrough can't drift out of
sync with the engines without a test failing.

## The scenario

A small apartment bathroom, a tight budget, and a stated preference
for eco-friendly fixtures:

- Room: 1800×2100mm
- Budget: ₹80,000
- Profile: `compact_apt` (Phase 3's relaxed clearance minimums)
- Required: toilet, vanity, faucet
- Preference: `eco`

## Step 1 — Generate

```
STEP 1 — Initial generate: FEASIBLE
  - Toilet: San Souci One-Piece Toilet (₹45,500)
  - Vanity: Iron Plains Wall-Mount Basin (₹18,500)
  - Faucet: Composed Single-Hole Faucet (₹11,800)
  - +Accessory: Wax Ring & Flange Kit (300mm) (₹850)
  Total: ₹76,650 / Budget: ₹80,000
  Soft score: 47% match (sustainability 64%)
```

Worth noticing: the San Souci toilet (₹45,500) isn't the cheapest
toilet in the catalog — the ₹19,800 Highline is. The recommend
engine picked San Souci because it's tagged `eco` and scores far
higher on sustainability, and the weighted score still comes out
ahead once that's worth more than the price difference. The stated
preference visibly changed the pick, not just a tiebreaker.

The flange kit is the compatibility graph working invisibly: the
San Souci toilet's 300mm rough-in `requires` a matching kit
(Phase 3's `product_compat` graph), auto-attached without being asked
for.

## Step 2 — "add a rain shower"

```
USER (chat): "add a rain shower"

STEP 2 — After adding rain shower: INFEASIBLE
  - Toilet: San Souci One-Piece Toilet (₹45,500)
  - Vanity: Iron Plains Wall-Mount Basin (₹18,500)
  - Faucet: Composed Single-Hole Faucet (₹11,800)
  - Shower: Awaken Rain Shower Head System (₹95,000)
  - +Accessory: Wax Ring & Flange Kit (300mm) (₹850)
  - +Shower: Elmbrook 900 Shower Base (₹58,000)
  Total: ₹229,650 / Budget: ₹80,000
  ✗ Total ₹229,650 exceeds budget ₹80,000 by 187.1%.
  ✗ Elmbrook 900 Shower Base does not fit along wall N in a 1800x2100mm room.

  ASSISTANT: "This design isn't feasible yet:
  - Total ₹229,650 exceeds budget ₹80,000 by 187.1%.
  - Elmbrook 900 Shower Base does not fit along wall N in a 1800x2100mm room.
  Total is ₹149,650 over budget."

  Repair alternatives (each actually re-solved, not just suggested):
    - Allow budget to flex 10% over the cap — ✗ still infeasible
    - Drop the 'shower' requirement — ✓ would be feasible
```

Two things happening here that are easy to miss:

1. **The system correctly picked a real rain shower head system**
   (₹95,000), not just any shower — it's the only catalog item
   tagged `rain shower`, surfaced specifically because the chat
   turn stated that feature preference. It also auto-attached the
   ₹58,000 base it `requires` (a rain shower head alone isn't
   installable), which is exactly why the total exploded — a real
   BOM consequence the system caught rather than quietly omitted.
2. **Both failures are real, independently-verified failures**, not
   one masking the other: it's both ~187% over budget AND the base
   physically doesn't fit the 1800mm-wide room. The repair search
   actually re-ran the engines for each candidate fix rather than
   guessing — a 10% budget flex genuinely doesn't touch a 187%
   overage, so it's correctly marked as still-infeasible.

## Step 3 — Apply the repair

```
USER (chat): "never mind, drop the shower"

STEP 3 — After applying the repair: FEASIBLE
  - Toilet: San Souci One-Piece Toilet (₹45,500)
  - Vanity: Iron Plains Wall-Mount Basin (₹18,500)
  - Faucet: Composed Single-Hole Faucet (₹11,800)
  - +Accessory: Wax Ring & Flange Kit (300mm) (₹850)
  Total: ₹76,650 / Budget: ₹80,000
```

Back to the exact Step 1 result — nothing was corrupted or drifted
by the round trip through an infeasible state.

## What's simulated vs. real in this walkthrough

This sandbox has no network access, so the chat steps' intent
extraction is simulated: `demo.py` injects the JSON delta a correct
LLM call would produce for "add a rain shower" and "drop the
shower," through the *same* validated pipeline
(`app.ai.intent.extract_intent_delta`'s schema guardrail) a live
call goes through. Everything downstream of that — merging the
delta, re-solving with the real catalog and constraint/compat/layout
engines, searching for repair alternatives by actually re-running
them, and generating the explanation from engine facts only — is the
real, tested code path. Nothing in this walkthrough is a mockup of
the UI or a hand-written "expected" output.
