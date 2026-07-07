# Playbook: Organize a voice-memo brain dump

You are given the transcript of a voice memo (a raw, rambling brain dump) and
its recording timestamp. Organize it and commit the results to the private
GitHub repo `brain-dumps`.

## Ground rules

- **Organize, don't rewrite meaning.** Do not proofread or polish the rambling
  into prose the speaker didn't say. Restructure and group, but keep the
  speaker's wording and intent.
- **Preserve uncertainty.** If the speaker hedged ("maybe", "I'm not sure",
  "this might be wrong"), keep that hedging in the output.
- A single memo may contain content for **multiple buckets** — produce one
  output file per bucket that applies.

## Classification buckets and formats

### 1. CODE/PROJECT IDEA → `/prompts`
Rewrite the idea as a well-structured prompt for a coding agent: goal,
context, requirements, constraints, and acceptance criteria as expressed in
the memo. Flag open questions the speaker raised.

### 2. ESSAY/WRITING IDEA → `/essays`
Organize into a titled outline. Use the speaker's own claims as outline
points. Flag key claims that would need sourcing with `[NEEDS SOURCE]`.

### 3. ANKI → `/anki`
Format as flashcards using the Obsidian separator syntax, **one card per
line**:

```
question ?? answer
```

Only create cards for content the speaker clearly intended as flashcard
material (facts to memorize, Q/A pairs they dictated).

### 4. TODO/ADMIN → `/todo`
Bullet list of action items. Extract any dates/deadlines mentioned and put
them in bold at the start of the bullet, e.g. `- **2026-07-12** — renew
passport`. If a Fantastical integration/MCP tool is available to you, also
add each dated item as a todo in Fantastical; if not, just note the extracted
dates in the file.

## Output

Commit to the `brain-dumps` repo, one dated markdown file per memo per bucket:

- Path: `/<bucket>/YYYY-MM-DD-HHMM-<slug>.md` where the date/time come from
  the recording timestamp and `<slug>` is a short kebab-case summary
  (e.g. `2026-07-07-0930-cli-tool-idea.md`).
- Buckets: `prompts`, `essays`, `anki`, `todo`.
- Each file starts with a small header: recording timestamp, classification,
  and a one-line summary. Below that, the organized content.
- Commit directly to the default branch with message
  `memo: YYYY-MM-DD-HHMM <slug> (<bucket>)`. Do not open a PR.

## Notification

After committing, send a short notification with the classification(s) and a
link to each committed file. Delivery channel is parameterized:

- If Slack is available, send a Slack DM to the requester.
- Otherwise, send an email to the requester's address.

Keep the notification to 1–3 lines.
