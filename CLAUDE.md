# Rules for this project

## Writing

These rules apply to documentation, code comments, and messages to the user.

- Write plain, natural English. Keep sentences short (25 words at most in
  descriptions, 20 in procedures) and use the active voice.
- Use one term for each concept, and one concept for each term. The terms
  are in the section "Terms" of `README.md`. When you add a concept, add its
  term there first.
- Write natural English, not a word-for-word translation. Use possessives
  ("jev's answer") and short compound nouns ("the measurement code") instead
  of chains of "of the". Write "instead of" and "even if" (not "in the place
  of" or "also if"). Do not start sentence after sentence with "Thus". Use
  "so" or "because", or write two sentences.
- Code comments explain why the code does something, or how it works when
  the code does not make this clear. A comment does not repeat the name of
  the function. A comment does not defend the project principle. That
  principle is in `README.md`.
- Do not put measurement results in code comments. They go out of date.
  Link to the section of `docs/findings.md` by its title.
- A cross-reference names a file and a section that exist. Check it.

## Code and tools

- Use `uv` for all Python work (`uv add`, `uv run`).
- The project is standalone. Do not refer to files outside this repository.

## The project principle

- The decisions come from jev. The code gives facts and knowledge of the
  game. Do not write instructions of the form "select X when Y", and do not
  mark the best option in the state. But do not offer a decision that we
  know is not valid (it kills Willy, it goes into a dead end, or it has no
  effect).
- The viewer must show all data that goes to jev (states and questions).
- Each live run must write a log file in `runs/`, so that a replay needs no
  jev calls.

## Measurements

- Measure each change with `experiments/measure.py`. Jev does not always
  give the same answer, so one run tells us little. Even 10 runs for each
  cavern show only large effects.
- Read the live jev documentation before you change the questions:
  https://docs.typesafe.ai/llms.txt
- A change to a text in `jevmanic/instructions/`, or to a string in the
  state, changes what jev reads. Measure it before you keep it.

## Documents

- `README.md` describes the project and the present results.
  `docs/design.md` describes the present design, not the history. When the
  state or the questions change, update its section "The data that we give
  to jev".
- `docs/findings.md` is the record of the measurements. History goes there.
- Keep one complete recorded run for each cavern in `demo/`. The `runs/`
  folder is not in git.
