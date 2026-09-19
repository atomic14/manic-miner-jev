# Rules for this project

- Write all documentation, code comments, and messages to the user in
  Simplified Technical English (ASD-STE100): short sentences, active voice,
  one meaning for each word, no unnecessary words.
- Use `uv` for all Python work (`uv add`, `uv run`).
- The project is standalone. Do not refer to files outside this repository.
- The viewer must show all data that goes to jev (state and questions).
- Each live run must write a log file in `runs/`, so that a replay needs no
  jev calls.
- Read the live jev documentation before you change the questions:
  https://docs.typesafe.ai/llms.txt
- `README.md` describes the present design, not the history. When the state
  or the questions change, update the section "The data that we give to jev".
- Keep one complete recorded run for each cavern in `demo/`. The `runs/`
  folder is not in git.
