---
name: session-handoff
description: >
  Write a handoff package so the NEXT session can start without re-deriving
  anything: what changed, the exact repo/environment state, what is unresolved,
  the open questions that need the user's answer, and the working conventions
  agreed in this session. Use at the end of a working session, before a context
  handover, or when the user asks to "wrap up", "hand off", "write a summary of
  this session", "what should the next session know". Trigger phrases: "handoff",
  "session summary", "wrap up the session", "prepare for the next session",
  "write the handoff".
---

# Session handoff

Produce a handoff package a *cold* session can act on. The reader has no memory
of this conversation and cannot ask follow-up questions.

## The test this has to pass

> Could someone who was not here resume the work tomorrow, make the next change
> correctly, and not re-litigate a decision that was already settled?

Everything below serves that. If a section would not change what the next session
*does*, cut it.

## Where it goes

Write to `temp/HANDOFF_<YYYY-MM-DD>.md` if `temp/` exists; otherwise ask before
creating a directory. **Check whether the target directory is gitignored**
(`git check-ignore -v <path>`) and say so in your reply — a handoff the user
expects to survive a fresh clone, but which git cannot see, is a silent failure.

If a handoff for the same date already exists, update it rather than adding a
second file.

## Rule 1 — verify, never summarise from memory

**Every factual claim must be re-checked against the repo before it goes in.**
Conversation memory drifts; a handoff that asserts something false is worse than
no handoff, because the next session will trust it.

At minimum, run and use the real output:

```bash
git status --short                  # working tree, exactly
git log --oneline -8                # what actually landed
git branch --show-current           # and whether it is pushed
<the project's test command>        # real numbers, not "tests pass"
```

Add whatever the project needs to prove its own state — installed-vs-source
diffs, a build artifact's freshness, a generated file matching its source. Prefer
a command whose output you paste over a sentence you wrote.

If something could not be verified, **say that explicitly** rather than
softening it. "Not re-run since X" is useful; a confident claim that turns out to
be stale costs the next session hours.

## Rule 2 — write down what was DECIDED, not just what was done

A diff shows what changed. It does not show which alternatives were rejected, so
the next session re-proposes them. For each significant decision, one line each:

- what was chosen
- what was rejected, and **why** — this is the part that stops the loop
- whether it is settled or still provisional

Mark anything a later event **superseded**. A decision recorded as current when it
has actually been overtaken is the most expensive kind of stale note.

## Rule 3 — separate "open" from "blocked" from "unknown"

These need different actions and must not be mixed:

| | Meaning | What the next session does |
|---|---|---|
| **Open** | Known work, nobody is blocking it | Pick it up |
| **Blocked** | Waiting on a person, a release, an upstream merge | Check the blocker first, do not start |
| **Open question** | Needs a decision only the user can make | **Ask** — do not assume |

Open questions must be phrased so the user can answer them directly, with the
options and the consequence of each. A question the next session cannot act on
without another round trip is not finished.

## Rule 4 — carry the working conventions

The next session will otherwise default to its own habits and the user will have
to correct the same things again. Record, concretely:

- **Tone and format** the user has asked for, including anything active in the
  environment (a communication-style plugin, a hook, a caveman/brevity mode) —
  and note that a hook-driven style may not survive into the next session unless
  it re-fires.
- **How files are edited here** — comment density and voice, whether *why* is
  written next to the *what*, docstring conventions, whether deleted machinery is
  replaced by an explanatory comment or removed silently.
- **Scope discipline** the user has enforced: what they want to run themselves,
  what they want asked about first, what is out of bounds.
- **Landmines** with the fix, not just the symptom: build artifacts that resurrect
  deleted files, caches that must be cleared, a step that is easy to skip and
  fails silently.

Quote the user where their own wording is clearer than a paraphrase.

## Structure

Use this order. Drop a section only if genuinely empty; say so rather than
omitting it silently.

1. **State in one paragraph** — where things stand, and the single most important
   thing to know.
2. **What changed this session** — grouped by area, each with the *why*, not a
   file list. A reader can get the file list from git.
3. **Verified state** — pasted command output: branch, tree, tests, environment.
   Include what was *not* verified.
4. **Decisions** — chosen / rejected / why / settled or provisional.
5. **Open items** — split per Rule 3.
6. **Open questions for the user** — numbered, with options and consequences.
7. **Working conventions** — per Rule 4.
8. **Where to look** — the two or three files a cold session should read first,
   in order, and what each is for. Be honest about which are stale.
9. **How to verify you are set up** — the commands that prove the environment is
   right, with expected output.

## Also do this

- **Point at the existing docs rather than duplicating them.** If the project has
  a guide, a plan, or a changelog, the handoff should say which to read and in
  what order. Duplicated prose drifts and then contradicts.
- **Update those docs too** if this session changed what they describe. A handoff
  that is correct while the guide beside it is wrong just moves the problem.
- **Reply with the essentials in the chat as well.** The user may hand the file to
  a new session without reading it, so a short spoken summary — state, blockers,
  open questions — earns its place.
