# Take-home: Router Rescue

Thanks for making time for this.

**Please cap yourself at 6 hours.** If you hit the cap, stop and write up what you have.
I would much rather read honest partial work than a rushed submission that looks complete.
Running out of time is a legitimate result and I will grade it as one.

**Use any AI tool you like.** I use them too. I am interested in your judgment, not in
whether you typed every character yourself.

---

## Background

We run an AI assistant inside a manufacturing ERP. When a user asks a question, a
**router** picks one of ~60 pre-built query tools — `purchase_po_count`,
`inventory_stock_by_item`, and so on. Each tool is a safe parameterised database query.

Today that router scores each tool by how many of its keyword phrases appear in the
query, with a small boost when the user's verb signals whether they want a list or a
number. It is fast, fully deterministic, and easy to audit, which we value. It is also
getting unreliable as the tool catalog grows, which we do not.

Your job is to work out **how** it is unreliable, and what to do about it.

---

## What you have

| File | What it is |
|---|---|
| `tools.json` | 62 tool definitions — id, module, description, keywords, output type, parameters |
| `queries.txt` | 150 real user queries, **unlabeled** |
| `baseline.py` | The router that runs today, simplified. Run `python baseline.py --all` |

`baseline.py` needs **Python 3.9+ and nothing but the standard library**. Check it runs:

```
python3 baseline.py "how many purchase orders are pending"
python3 baseline.py --all
```

Start by reading it — several of its behaviours look like bugs and are not, and at least
one looks fine and is not.

Each query in `queries.txt` has a stable id (`q001`…`q150`). Please key your labels to
those ids rather than to the query text.

**There is no database in this exercise, and nothing to install.** The whole task is
text in, tool name out. `tools.json` describes what each tool *would* query in
production, but the SQL has been stripped — you never connect to anything, and you will
not need credentials, a server, or sample data. Plain files and Python are all it takes.

---

## What to deliver

### 1. `labels.csv` — your ground truth

A plain CSV file. One row per query, keyed by its id. Decide what each of the 150
queries *should* route to.

**You design the set of labels yourself** — the columns, and the vocabulary of values
they can take. I am deliberately not giving you a template. `tool_name` on its own will
not cover every case you find, and working out what the other cases are is a real part
of this task, arguably the main part. Include your confidence in each label, and leave
yourself a notes column.

### 2. `LABELING_RULES.md` — the rules you followed

Write these **as you go**, not afterwards. Every time a query forces a judgment call,
record the call and your reasoning. If you change your mind partway through, say so, and
say whether you went back and re-labeled the earlier ones.

This document matters as much to me as the code.

### 3. `router.py` — your improved router

Hard constraints:

- **No network calls at inference time.** No hosted LLM API in the query path. You may
  use anything you like offline, or at build time.
- **Median latency under 200 ms** per query on a laptop CPU.
- Must return `(tool_name, confidence, reason)` — where `reason` is a short
  human-readable string explaining why that tool was chosen.

### 4. `evaluate.py`

Runs the baseline and your router against your labels and prints a comparison.
I will run this myself, so it should work from a clean checkout. Document any setup.

### 5. `REPORT.md` — two pages maximum

Must contain:

- **The numbers.** Baseline versus yours, broken down however you think is most honest.
- **The five worst remaining failures**, with root cause for each — not just "it picked
  the wrong tool", but *why your approach was structurally unable to get it right*.
- **Three things you tried that did not work**, and roughly what each cost you in time.
- **What you would do with another week**, in priority order.
- **What is wrong with this assessment.** Where is my setup unfair, unrealistic, or
  measuring the wrong thing? I am asking sincerely, and I will read this section closely.

---

## How I will grade it

| Weight | On |
|---|---|
| 40% | Your labels and labeling rules |
| 25% | The report — honesty and depth of error analysis |
| 20% | The router |
| 15% | The follow-up conversation |

**The code is the smallest part.** A router that improves modestly, paired with a sharp
and honest analysis of why it still fails, scores far better here than a high number with
a thin explanation.

---

## One request

Commit as you work — at least every 45 minutes, including attempts you later abandon.
I read commit history, and dead ends in it are a positive signal, not a negative one.

---

## Submitting

Share it as a **git repository** — GitHub, GitLab, whichever you prefer — and send me
the link. A zip is fine if a repo is genuinely inconvenient, but you would be giving up
the commit history, which is part of what I look at.

Deadline and my email address are in the covering message. If you have lost it, reply to
whatever address this reached you from.

## Afterwards

We will do a 30-minute call where you walk me through it and we poke at it together.
Have your editor open. Expect me to ask you to change something live and to talk me
through a couple of individual labels.

Good luck — and please do email me if anything here is ambiguous. Asking is not a penalty.
