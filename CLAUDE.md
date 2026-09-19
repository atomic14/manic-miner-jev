# Rules for this project

- Write all documentation, code comments, and messages to the user in
  Simplified Technical English (ASD-STE100): short sentences, active voice,
  one meaning for each word, no unnecessary words.
- Use `uv` for all Python work (`uv add`, `uv run`).
- The project is standalone. Do not refer to files outside this repository.
- The viewer must show all data that goes to jev (state and questions).
- Each live run must write a log file in `runs/`, so that a replay needs no
  jev calls.
- The decisions must come from jev. The code gives facts and knowledge of the
  game. Do not write instructions of the form "select X when Y", and do not
  mark the best option in the state. But do not offer a decision that we know
  is not valid (it kills Willy, it is a dead end, or it has no effect).
- Measure each change with `experiments/measure.py`. Jev does not always give
  the same answer, thus one run tells us little, and 3 runs for each cavern
  show only large effects.
- Read the live jev documentation before you change the questions:
  https://docs.typesafe.ai/llms.txt
- `README.md` describes the present design, not the history. When the state
  or the questions change, update the section "The data that we give to jev".
- Keep one complete recorded run for each cavern in `demo/`. The `runs/`
  folder is not in git.
