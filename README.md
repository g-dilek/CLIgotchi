# CLIgotchi — terminal mentor edition

A tiny virtual pet that lives in your terminal. Local only — save data stays in `~/.cligotchi/`.

## Run it

In PowerShell, open the `outputs` folder and run:

```powershell
py .\cligotchi.py
```

Use `py .\cligotchi.py --no-colour` for a plain-text terminal.

Progress is stored locally as `.cligotchi-state.json` in the folder where you launch it. The lessons are simulated: CLIgotchi checks only the text you enter and never runs a learner's Git or shell command.

## Run it

```bash
python3 ~/cligotchi/cligotchi.py
```

Or:

```bash
chmod +x ~/cligotchi/cligotchi.py
~/cligotchi/cligotchi.py
```

Needs an interactive terminal (a normal shell tab). First launch asks you to name the pet.

## Play to learn

- `learn` presents the next concept in a safe progression: orientation, project inspection, status, staging, commits, history, branches, and diffs.
- Correct answers award XP and game tokens. Lesson milestones evolve Byte from a booting egg to a CI dragon.
- `feed` adds food variety with distinct stats and programmer traits; three different foods in a day grant a replayable bonus.
- `play trace`, `play sprint`, and `play oracle` reinforce command recall and decision-making without touching a repository.
- `syllabus`, `status`, and `log` make progress visible to a learner or instructor.

Useful first commands: `help`, `learn`, `feed berries`, `play sprint`.

## Tiny custom coach hints (optional)

Every incorrect answer already receives a local, lesson-specific explanation—no internet or package installation required. For a custom one-sentence explanation in Byte's voice, opt in when launching the game:

```powershell
$env:OPENAI_API_KEY="your_key_here"
py .\cligotchi.py --coach
```

Coach mode sends only the simulated lesson prompt, the learner's answer, and the expected command to the OpenAI Responses API; it does not execute a command or send repository files. The game sends `store: false` and falls back to its local hint if there is no key, no connection, or an API error. Do not enter private information as a lesson answer. You may override the model with `CLIGOTCHI_COACH_MODEL`. The integration uses the [official Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create), which supports text input, instructions, output token limits, and `store` controls.
