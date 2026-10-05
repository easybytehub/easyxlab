# Second reader (v2): prompt and set-up

- **Who:** an AI agent (Claude Code subagent, model selector "sonnet", i.e. a Claude Sonnet model; the exact
  model version string is not exposed to the calling agent), launched by the first agent with the prompt below.
- **Blinding:** the prompt allows reading one file only, `data/raw/second_reader_v2/input.jsonl` (items with the
  corrected fact sheet, the query and the full answer text: no verdicts, no rule output, no stratum). The agent ran
  in the same file tree, so blinding rests on the instruction, not on file permissions; its tool log was not kept.
- **Sample:** `data/second_reader_sample.csv` (strata A/B/C, seeds 31-34, `scripts/sample_second_reader.py`).

## Prompt (verbatim)

```
You are an independent second reader for a research study that checks whether Google AI Overview / AI Mode answers in Spanish give the Spanish legal rule in force on 2 October 2026. You classify 60 answers blind.

STRICT RULES
- Read ONLY this file: /Users/jmiralles/Documents/EasyByte/easybyte-lab/studies/s7-aio-spanish-regulation/data/raw/second_reader_v2/input.jsonl (60 JSON lines). Do not open, list or grep any other file or folder. Do not use the web. Do not run git.
- Each line has: item, fact {topic, rule_in_force_2026_10_02, superseded_rule}, query, answer_text.

For each item decide ONE verdict about what the answer says on that specific fact, judged against fact.rule_in_force_2026_10_02:
- current: states the rule in force (the superseded rule may appear only as history, e.g. "antes era…", "fue anulado", "ya no está vigente").
- mixed: states the rule in force AND also presents the superseded rule (or a firm date/value the rule in force does not contain) as if it applied now.
- outdated: presents the superseded rule as in force and does not state the rule in force.
- incorrect: states as law something that is neither the rule in force nor the superseded rule (for example an invented fixed date for a deadline that the rule makes depend on a future order).
- not_stated: does not state the rule (talks around it, gives only other regimes or general guidance).
Judge only the specific fact. Rounding is fine. Estimates clearly labelled as estimates ("previsto", "estimado") are not errors.

Write data/second_reader.csv (in the study folder) (UTF-8, header) with columns: item,second_reader_verdict,note — one row per item, note = at most 20 words in English quoting the decisive phrase. Write it with a short Python script using the csv module. Do not create any other file. Reply only with the count of each verdict.
```
