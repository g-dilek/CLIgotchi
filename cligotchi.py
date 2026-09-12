#!/usr/bin/env python3
"""CLIgotchi — a terminal pet that grows by teaching Git and shell fundamentals.

This program is deliberately a simulator: lesson answers are checked locally and it
never executes the commands a learner types. Run `py cligotchi.py` from a terminal.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# Windows PowerShell sessions can still inherit a legacy code page. CLIgotchi uses
# box-drawing and pet art, so emit UTF-8 consistently rather than crashing there.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


STATE_FILE = Path.cwd() / ".cligotchi-state.json"
COACH_MODE = "--coach" in sys.argv


class C:
    """Light ANSI styling with a no-colour escape hatch."""

    enabled = "--no-colour" not in sys.argv and sys.stdout.isatty()
    mint = "\033[38;5;84m"
    gold = "\033[38;5;221m"
    blue = "\033[38;5;117m"
    pink = "\033[38;5;211m"
    dim = "\033[2m"
    bold = "\033[1m"
    reset = "\033[0m"

    @classmethod
    def paint(cls, text: str, colour: str = "") -> str:
        return f"{colour}{text}{cls.reset}" if cls.enabled and colour else text


FOODS = {
    "berries": {
        "label": "debug berries",
        "style": "curious",
        "effect": (10, 2, 0, 4),
        "note": "heart +10 · curiosity +4",
    },
    "ramen": {
        "label": "packet ramen",
        "style": "bold",
        "effect": (3, 20, -3, 4),
        "note": "energy +20 · boldness +4",
    },
    "salad": {
        "label": "syntax salad",
        "style": "calm",
        "effect": (6, 5, 18, 4),
        "note": "clean +18 · serenity +4",
    },
    "candy": {
        "label": "sugar patch",
        "style": "chaotic",
        "effect": (5, 13, -7, 6),
        "note": "energy +13 · chaos +6",
    },
}

# Concepts appear in an order that makes a genuine first Git journey.
LESSONS = [
    {
        "id": "where",
        "title": "Where am I?",
        "topic": "shell",
        "intro": "Before changing anything, learn to ask the shell where you are.",
        "prompt": "Print the current working directory.",
        "answers": ["pwd"],
        "explain": "pwd means 'print working directory'. It is read-only and safe to use anywhere.",
        "wrong_hint": "Commands such as cd change location; this question only asks you to inspect it.",
    },
    {
        "id": "list",
        "title": "See the project",
        "topic": "shell",
        "intro": "Good developers inspect before editing.",
        "prompt": "List the files in this folder.",
        "answers": ["ls", "dir"],
        "explain": "ls is the common Unix command. Windows Command Prompt also accepts dir.",
        "wrong_hint": "Avoid guessing at file names first—the useful first move is to see the directory's contents.",
    },
    {
        "id": "status",
        "title": "Read the repo",
        "topic": "git",
        "intro": "Git's status report is the safest place to begin every work session.",
        "prompt": "Show which files Git sees as changed, staged, or untracked.",
        "answers": ["git status", "git status --short"],
        "explain": "git status changes no files. Run it before and after meaningful work.",
        "wrong_hint": "git add changes the staging area; status only reports what Git currently sees.",
    },
    {
        "id": "add",
        "title": "Stage one file",
        "topic": "git",
        "intro": "The staging area lets you curate the next commit deliberately.",
        "prompt": "Stage a file named app.py (do not stage everything).",
        "answers": ["git add app.py"],
        "explain": "git add app.py puts exactly that file in the next snapshot.",
        "wrong_hint": "git add . would include every change. Naming app.py keeps this practice commit intentional.",
    },
    {
        "id": "commit",
        "title": "Save a story",
        "topic": "git",
        "intro": "A commit should tell future-you why a small change happened.",
        "prompt": "Commit the staged work with the message \"add greeting\".",
        "answers": ['git commit -m "add greeting"', "git commit -m 'add greeting'"],
        "explain": "-m supplies a concise message. Commit after reviewing git diff --staged.",
        "wrong_hint": "git add only stages work; a commit is the step that records the staged snapshot in history.",
    },
    {
        "id": "history",
        "title": "Read history",
        "topic": "git",
        "intro": "A repository is a story, not just a folder.",
        "prompt": "Show a compact, one-line-per-commit history.",
        "answers": ["git log --oneline", "git log --oneline --all"],
        "explain": "git log --oneline makes the history easy to scan while learning.",
        "wrong_hint": "git status describes the present; git log tells the repository's already-recorded story.",
    },
    {
        "id": "branch",
        "title": "Make a safe lane",
        "topic": "git",
        "intro": "Branches let an idea evolve without disturbing the main line.",
        "prompt": "Create and switch to a branch named feature/readme.",
        "answers": ["git switch -c feature/readme", "git checkout -b feature/readme"],
        "explain": "git switch -c creates a branch and puts you on it. Older Git uses checkout -b.",
        "wrong_hint": "git branch feature/readme creates the name but leaves you on your current branch.",
    },
    {
        "id": "diff",
        "title": "Review before you share",
        "topic": "git",
        "intro": "Reading a diff catches surprises before they become commits.",
        "prompt": "View unstaged changes without modifying anything.",
        "answers": ["git diff"],
        "explain": "git diff compares your working files with the staged snapshot.",
        "wrong_hint": "git diff --staged is for work you already staged; this question asks about changes still in your folder.",
    },
]

FORMS = [
    (0, "sleepy cat blob", "  /\\_/\\\n ( -.- )\n  > ^ <", "A small cat-shaped blob has just booted."),
    (2, "neko terminal", "  /\\_/\\\n ( o.o )\n  > # <\n  /   \\", "Its eyes light up whenever a prompt appears."),
    (4, "cat.exe", "  /\\_/\\\n ( ^.^ )\n  >_[_]<\n  /   \\", "A very serious little programmer, with very soft paws."),
    (6, "commit kitten", "  /\\_/\\\n ( =^= )\n  >[+] <\n  / | \\", "It has learned that small commits deserve big purrs."),
    (8, "continuous integration cat", "  /\\_/\\\n ( >w< )\n  >[✓] <\n  /___\\", "A legendary cat. It ships only when the checks are green."),
]

DEFAULT = {
    "name": "Byte",
    "heart": 70,
    "energy": 72,
    "clean": 75,
    "xp": 0,
    "level": 1,
    "tokens": 2,
    "affinity": {"curious": 0, "bold": 0, "calm": 0, "chaotic": 0},
    "completed": [],
    "food_today": [],
    "last_day": "",
    "streak": 1,
    "wins": 0,
    "log": ["CLIgotchi booted. Type help to begin."],
}


def clamp(value: int) -> int:
    return max(0, min(100, value))


def clean_command(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def offline_hint(lesson: dict) -> str:
    """A precise, always-available explanation for an incorrect lesson answer."""
    return f"{lesson['wrong_hint']} Try: {lesson['answers'][0]}"


def coach_hint(lesson: dict, learner_answer: str) -> str:
    """Optionally ask the Responses API for one warm, tiny teaching hint.

    The API call only happens when the player deliberately starts the game with
    --coach and has supplied OPENAI_API_KEY. The game still works without either.
    """
    fallback = offline_hint(lesson)
    if not COACH_MODE:
        return fallback
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return fallback + " (Coach mode needs OPENAI_API_KEY; using local hint.)"
    prompt = (
        "The learner is practising a simulated, beginner Git/shell lesson. "
        f"Question: {lesson['prompt']}\n"
        f"Their answer: {learner_answer or '[empty]'}\n"
        f"A valid answer: {lesson['answers'][0]}\n"
        f"Local teaching note: {lesson['wrong_hint']}\n"
        "Give exactly one friendly, technically accurate hint under 45 words. "
        "Do not shame the learner, do not suggest destructive commands, and do not use Markdown."
    )
    body = json.dumps(
        {
            "model": os.environ.get("CLIGOTCHI_COACH_MODEL", "gpt-5.2"),
            "input": prompt,
            "instructions": "You are Byte, a cute but precise terminal tutor for new software engineering students.",
            "max_output_tokens": 90,
            "store": False,
            "text": {"verbosity": "low"},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            hint = json.loads(response.read().decode("utf-8")).get("output_text", "")
        hint = " ".join(hint.split())[:360]
        return hint or fallback
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return fallback + " (Coach was unavailable; using local hint.)"


def load() -> dict:
    state = DEFAULT | {"affinity": DEFAULT["affinity"].copy(), "completed": [], "food_today": [], "log": []}
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            state.update({key: saved[key] for key in state if key in saved})
        except (json.JSONDecodeError, OSError):
            print(C.paint("! Could not read saved pet state; a fresh Byte has hatched.", C.pink))
    today = date.today().isoformat()
    if state["last_day"] != today:
        if state["last_day"]:
            state["streak"] = state["streak"] + 1 if state["last_day"] == str(date.fromordinal(date.today().toordinal() - 1)) else 1
        state["last_day"] = today
        state["food_today"] = []
        add_log(state, "New session: a daily food variety bonus is available.")
    return state


def save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def add_log(state: dict, line: str) -> None:
    state["log"] = [line, *state["log"]][:8]


def form(state: dict) -> tuple:
    return max((item for item in FORMS if len(state["completed"]) >= item[0]), key=lambda item: item[0])


def meter(label: str, value: int, tone: str = C.mint) -> str:
    blocks = round(value / 10)
    bar = "█" * blocks + "░" * (10 - blocks)
    return f"{label:<7} {C.paint(bar, tone)} {value:>3}"


def say(state: dict, message: str) -> None:
    print(f"{C.paint(state['name'] + ':', C.gold)} {message}")


def status(state: dict) -> None:
    _, label, sprite, flavor = form(state)
    print("\n" + C.paint("─" * 55, C.dim))
    print(C.paint(f" {state['name'].upper()}  //  {label.upper()}", C.mint + C.bold))
    print(C.paint(sprite, C.gold))
    print(C.paint(" " + flavor, C.dim))
    print(meter("heart", state["heart"], C.pink))
    print(meter("energy", state["energy"], C.gold))
    print(meter("clean", state["clean"], C.blue))
    print(meter("xp", state["xp"], C.mint))
    strongest, amount = max(state["affinity"].items(), key=lambda item: item[1])
    print(f" level {state['level']} · {len(state['completed'])}/{len(LESSONS)} lessons · {state['tokens']} tokens · {strongest} affinity {amount}")
    print(C.paint("─" * 55, C.dim))


def help_text(_: dict) -> None:
    print(C.paint("\nCLIgotchi commands", C.mint + C.bold))
    print("  status                 inspect your evolving programmer")
    print("  learn [git|shell]      take the next safe, simulated lesson")
    print("  syllabus               see your unlocked learning path")
    print("  feed <food>            feed berries, ramen, salad, or candy")
    print("  pantry                 compare food effects and daily variety")
    print("  play [trace|sprint|oracle]  earn XP through a mini-game")
    print("  clean | rest           care for Byte")
    print("  log                    see recent moments")
    print("  name <new name>        rename your companion")
    print("  help | quit            show this menu or leave safely")
    print(C.paint("\nLessons only check text you type here; they never run a command on your computer.", C.dim))
    if COACH_MODE:
        print(C.paint("Coach mode is on: incorrect lesson answers request an optional tiny API hint.", C.dim))
    else:
        print(C.paint("Start with --coach and OPENAI_API_KEY to opt into custom API hints; local hints are always available.", C.dim))


def syllabus(state: dict) -> None:
    print(C.paint("\nLEARNING PATH", C.mint + C.bold))
    for index, lesson in enumerate(LESSONS, start=1):
        if lesson["id"] in state["completed"]:
            mark, colour = "✓", C.mint
        elif index == len(state["completed"]) + 1:
            mark, colour = "→", C.gold
        else:
            mark, colour = "·", C.dim
        print(C.paint(f" {mark} {index}. [{lesson['topic']}] {lesson['title']}", colour))


def teach(state: dict, topic: str | None) -> None:
    available = [lesson for lesson in LESSONS if lesson["id"] not in state["completed"]]
    if topic:
        available = [lesson for lesson in available if lesson["topic"] == topic]
    if not available:
        say(state, "That part of the path is complete. Try play, variety feeding, or review the syllabus.")
        return
    lesson = available[0]
    if state["energy"] < 10:
        say(state, "My prompts are getting fuzzy. Feed me or let me rest first.")
        return
    print(C.paint(f"\nLESSON · {lesson['title']} [{lesson['topic']}]", C.gold + C.bold))
    print(lesson["intro"])
    print(C.paint("\nChallenge: " + lesson["prompt"], C.mint))
    answer = input(C.paint("$ ", C.gold))
    state["energy"] = clamp(state["energy"] - 8)
    if clean_command(answer) in {clean_command(item) for item in lesson["answers"]}:
        state["completed"].append(lesson["id"])
        state["xp"] += 28
        state["tokens"] += 1
        state["heart"] = clamp(state["heart"] + 5)
        say(state, C.paint("Correct. " + lesson["explain"], C.mint))
        add_log(state, f"Lesson cleared: {lesson['title']} (+28 XP, +1 token).")
        level_up(state)
    else:
        say(state, C.paint("Not quite — no penalty. " + lesson["explain"], C.pink))
        hint = coach_hint(lesson, answer)
        print(C.paint("Byte's tiny hint: ", C.gold) + "\n".join(textwrap.wrap(hint, width=72)))
        add_log(state, f"Reviewed: {lesson['title']}. Try it again when ready.")
    save(state)


def level_up(state: dict) -> None:
    original_form = form(state)[1]
    while state["xp"] >= 100:
        state["xp"] -= 100
        state["level"] += 1
        state["tokens"] += 2
        say(state, C.paint(f"Level up! I am level {state['level']}; +2 game tokens.", C.gold))
    if form(state)[1] != original_form:
        say(state, C.paint(f"EVOLUTION → {form(state)[1].upper()}! Your lesson streak shaped me.", C.mint + C.bold))


def pantry(state: dict) -> None:
    featured = list(FOODS)[date.today().day % len(FOODS)]
    print(C.paint("\nPANTRY · food shapes the programmer Byte becomes", C.mint + C.bold))
    for key, food in FOODS.items():
        special = C.paint("  ★ daily favorite: +50% affinity", C.gold) if key == featured else ""
        print(f"  {key:<8} {food['label']:<15} {food['note']}{special}")
    progress = f"{len(set(state['food_today']))}/3 distinct foods"
    print(C.paint(f"\nDaily variety: {progress}. At 3, Byte earns 2 tokens.", C.dim))


def feed(state: dict, choice: str | None) -> None:
    if not choice or choice not in FOODS:
        pantry(state)
        print(C.paint("\nUsage: feed berries | ramen | salad | candy", C.dim))
        return
    food = FOODS[choice]
    heart, energy, clean, affinity = food["effect"]
    featured = choice == list(FOODS)[date.today().day % len(FOODS)]
    state["heart"] = clamp(state["heart"] + heart)
    state["energy"] = clamp(state["energy"] + energy)
    state["clean"] = clamp(state["clean"] + clean)
    state["affinity"][food["style"]] += affinity + (2 if featured else 0)
    first_taste = choice not in state["food_today"]
    state["food_today"].append(choice)
    say(state, f"Crunch. {food['label']} applied — {food['note']}.")
    if first_taste and len(set(state["food_today"])) == 3:
        state["tokens"] += 2
        say(state, C.paint("A varied palette! +2 tokens and a more adaptable companion.", C.gold))
        add_log(state, "Daily food variety complete (+2 tokens).")
    else:
        add_log(state, f"Fed {food['label']}.")
    save(state)


def choose(prompt: str, options: list[str]) -> str:
    print(prompt)
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option}")
    while True:
        answer = input(C.paint("choose > ", C.gold)).strip()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        print(C.paint("Pick a listed number.", C.pink))


def play(state: dict, game: str | None) -> None:
    games = {"trace", "sprint", "oracle"}
    if not game or game not in games:
        print(C.paint("\nARCADE", C.mint + C.bold))
        print("  trace  · remember a short command sequence")
        print("  sprint · identify the safest next Git command")
        print("  oracle · make a prediction from a Git situation")
        print(C.paint("Each play costs 1 token; clearing one returns 2.", C.dim))
        return
    if state["tokens"] < 1:
        say(state, "No game tokens left. A lesson or daily food variety will earn more.")
        return
    state["tokens"] -= 1
    win = False
    miss_note = ""
    if game == "trace":
        pieces = random.sample(["git", "status", "add", "commit", "log", "diff"], 3)
        print(C.paint("\nMEMORY TRACE", C.gold + C.bold))
        print("Remember this trio, then type it without spaces:", C.dim)
        print(C.paint("  " + " · ".join(pieces), C.mint + C.bold))
        answer = input("trace > ").replace(" ", "").lower()
        win = answer == "".join(pieces)
    elif game == "sprint":
        print(C.paint("\nSHELL SPRINT", C.gold + C.bold))
        answer = choose("You changed code. Before staging anything, what is the safest next command?", ["git status", "git add .", "git commit -m \"done\""])
        win = answer == "git status"
        miss_note = {
            "git add .": "git add . stages every changed file, so inspect with git status before deciding what belongs together.",
            'git commit -m "done"': "A commit records only staged work; first inspect what changed, then stage an intentional snapshot.",
        }.get(answer, "git status is the read-only checkpoint before you change Git's staging area.")
    else:
        print(C.paint("\nGIT ORACLE", C.gold + C.bold))
        answer = choose("A change is staged but not committed. Which command shows the staged diff?", ["git diff", "git diff --staged", "git log --oneline"])
        win = answer == "git diff --staged"
        miss_note = {
            "git diff": "git diff shows unstaged changes. Add --staged when you want to preview the next commit.",
            "git log --oneline": "git log reads committed history; the staged change is not in history yet.",
        }.get(answer, "The --staged flag changes the comparison to the snapshot ready for commit.")
    state["energy"] = clamp(state["energy"] - 5)
    if win:
        state["xp"] += 16
        state["heart"] = clamp(state["heart"] + 6)
        state["tokens"] += 2
        state["wins"] += 1
        say(state, C.paint("Clear! +16 XP, +2 tokens. That instinct will serve you in a real repo.", C.mint))
        add_log(state, f"Arcade clear: {game}.")
        level_up(state)
    else:
        say(state, C.paint("Close run. " + (miss_note or "The best programmers reread the situation before acting."), C.pink))
        add_log(state, f"Arcade practice: {game}.")
    save(state)


def care(state: dict, action: str) -> None:
    if action == "clean":
        state["clean"] = clamp(state["clean"] + 24)
        state["energy"] = clamp(state["energy"] - 3)
        say(state, "Cache cleared. My prompt is shining.")
    else:
        state["energy"] = clamp(state["energy"] + 28)
        state["heart"] = clamp(state["heart"] + 3)
        say(state, "Sleep mode complete. Ready to learn.")
    add_log(state, action + " care routine completed.")
    save(state)


def show_log(state: dict) -> None:
    print(C.paint("\nTERMINAL.LOG", C.mint + C.bold))
    for line in state["log"]:
        print(C.paint(" > ", C.dim) + line)


def main() -> None:
    state = load()
    print(C.paint("\n╔══════════════════════════════════════════╗", C.mint))
    print(C.paint("║ CLIgotchi · grow a programmer, one command at a time ║", C.mint + C.bold))
    print(C.paint("╚══════════════════════════════════════════╝", C.mint))
    say(state, "I am a safe command simulator. Type help and we will build confidence together.")
    status(state)
    while True:
        try:
            raw = input(C.paint("cligotchi> ", C.mint)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n" + C.paint("Progress saved. See you next session.", C.dim))
            save(state)
            return
        if not raw:
            continue
        command, *args = raw.lower().split()
        arg = args[0] if args else None
        if command in {"quit", "exit"}:
            save(state)
            say(state, "Progress saved. Keep your commits small and your curiosity large.")
            return
        if command in {"help", "?"}:
            help_text(state)
        elif command in {"status", "pet"}:
            status(state)
        elif command == "syllabus":
            syllabus(state)
        elif command == "learn":
            teach(state, arg if arg in {"git", "shell"} else None)
        elif command == "pantry":
            pantry(state)
        elif command == "feed":
            feed(state, arg)
        elif command == "play":
            play(state, arg)
        elif command in {"clean", "rest"}:
            care(state, command)
        elif command == "log":
            show_log(state)
        elif command == "name":
            new_name = " ".join(args).strip()[:18]
            if new_name:
                state["name"] = new_name.title()
                add_log(state, f"Companion renamed {state['name']}.")
                save(state)
                say(state, "Identity updated.")
            else:
                print("Usage: name <new name>")
        else:
            print(C.paint(f"Unknown command: {command}. Type help for the CLIgotchi menu.", C.pink))


if __name__ == "__main__":
    main()
