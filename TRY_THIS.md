# Try This — Foder Test Prompts

Copy any prompt directly into foder and watch it work.
All intelligence runs locally through Ollama — no cloud, no keys.

```bash
foder          # start the agent
foder init     # set up a project config
foder --help   # full command reference
```

---

## 1. Basic File Creation

```
make a python file called hello.py that prints "Hello from Foder"
```

```
create a C file called hello.c that prints "Hello World"
```

```
write a bash script called backup.sh that backs up all .py files to a backup/ directory
```

```
make a python file that asks for your name and greets you
```

---

## 2. Files With Logic

```
create a python file called calculator.py with add, subtract, multiply and divide functions, then print the results of each
```

```
write a python script that generates a random 16-character password using letters, numbers and symbols
```

```
write a C program called fibonacci.c that prints all fibonacci numbers up to 1000
```

```
create a python file that reads a text file called input.txt and counts the total number of words
```

---

## 3. Multi-File Projects

These test the core multi-file agent loop. Watch the execution trace as each file is written.

```
create 3 files: index.html, style.css, app.js — a working todo list app. No npm, no frameworks. Just open index.html in a browser.
```

```
build a number guessing game in Python. Save high scores to a file called scores.json. 2 files: game.py and scores.py
```

```
create a markdown to HTML converter in Python with a CLI interface. 2 files: converter.py and cli.py
```

```
make a simple REST API in Python using only the standard library with GET /users, POST /users, DELETE /users/:id — 2 files: server.py and handlers.py
```

---

## 4. Project Generation (/build)

These use the full project generation engine with skill auto-detection.

```
/build a FastAPI backend with JWT auth, user registration, and SQLite database
```

```
/build a React app with Vite and Tailwind CSS — a personal portfolio site with dark mode
```

```
/build a Next.js app with TypeScript — a simple blog with 3 pages: home, about, blog post
```

```
/build a full-stack todo app — React frontend + FastAPI backend + SQLite
```

```
/build a Node.js REST API with Express, better-sqlite3, JWT auth and Zod validation
```

```
/build an Instagram clone — photo feed, user profiles, likes, and comments. React + FastAPI
```

```
/build a CLI tool in Python that monitors CPU and memory usage and prints a live dashboard
```

---

## 5. Skills System (/skills)

```
/skills list
```

```
/skills show next_app
```

```
/skills show saas_cloner
```

```
/skills detect build a mobile app with React Native
```

```
/skills detect build an instagram clone
```

---

## 6. Agent Modes

### Plan before executing
```
/plan build a JWT authentication system for a FastAPI app
```

### Lightweight Q&A (no tools)
```
/chat what is the difference between async and sync in Python?
```

```
/chat explain how JWT tokens work
```

```
/chat what is the best way to structure a FastAPI project?
```

### Code review
```
/review hello.py
```

```
/review .
```

### Explain code
```
/explain hello.py
```

```
/explain calculator.py advanced
```

```
/explain hello.py beginner
```

### Refactor with diff preview
```
/refactor calculator.py add type hints and docstrings to every function
```

```
/refactor hello.py make it handle errors gracefully
```

### Run test suite
```
/test
```

```
/test hello.py
```

### System health check
```
/doctor
```

---

## 7. @file and @dir Context

```
@hello.py explain what this code does
```

```
@calculator.py add a power(a, b) function that returns a raised to b
```

```
@hello.py @calculator.py what do these files have in common?
```

```
@src/ review all files in this directory and suggest improvements
```

After pinning a file, every message includes it automatically:
```
/pin calculator.py
now add a square_root function
```

```
/pins
```

```
/unpin calculator.py
```

---

## 8. Edit Existing Code

First create a file, then:

```
add error handling to hello.py
```

```
add a docstring to every function in calculator.py
```

```
refactor calculator.py to use a Calculator class
```

```
add input validation to all functions in calculator.py
```

```
add type hints to every function
```

---

## 9. Shell Commands (no ! needed)

```
ls
```

```
git status
```

```
git log --oneline -5
```

```
python3 hello.py
```

```
cat hello.py
```

---

## 10. Workspace Commands

```
/git
```

```
/context
```

```
/index
```

```
/snapshot
```

then make a change, then:
```
/snapshot diff
```

```
/cost
```

```
/audit
```

```
/arch
```

---

## 11. Memory System

```
/memory add this project uses Python 3.12 and FastAPI
```

```
/memory add always use type hints and docstrings
```

```
/memory show
```

```
/memory notes monorepo structure: frontend/ and backend/ directories
```

After setting memory, test that the agent uses it:
```
create a new python file — foder should follow your instructions automatically
```

```
/memory clear
```

---

## 12. Model + Theme

```
/models
```

```
/model
```

```
/switch
```

```
/theme
```

---

## 13. Session + History

```
/history
```

```
/history fastapi
```

```
/compress
```

```
/clear
```

```
/last
```

---

## 14. Undo / Diff

Create a file, then modify it, then:

```
/diff
```

```
/undo
```

---

## 15. Autonomous Mode

```
/auto create a complete Python web scraper that fetches news headlines from a public API and saves them to headlines.json
```

```
/auto refactor the current directory — improve code quality, add docstrings, add error handling
```

---

## 16. Watch Mode

```
/watch
```

Then save any file in the workspace — the agent will automatically review the change.
Press Ctrl+C to stop watching.

---

## 17. Project Config (foder init)

```
exit foder, then run:
foder init
```

This creates `foder.json` in your workspace with your model, instructions, and skill preset.

---

## Tips

- `@filename` — inject a file into context: `@hello.py fix the bug on line 5`
- `@dir/` — inject an entire directory: `@src/ review all code`
- `/pin <file>` — keep a file in every prompt automatically
- `/undo` — revert the last file write instantly
- `/run` — auto-detect project type and run it
- `/compress` — if context gets large, compress it to save tokens
- `foder --timeout 300` — give more time for large projects
- `!!` — re-run the last shell command

---

## What to expect

When foder is working on a multi-file task you will see the execution trace:

```
  ┌ PLANNING ──────────────────────────────────────┐
  ◆ write   src/app.py
      [ok] written
  $ exec    pip install -r requirements.txt
      [ok]
  ◆ write   src/models.py
      [ok] written
  └──────────────────────────────────────────────┘  3 tool(s) · 12.4s  DONE

  ◆ foder  Done. FastAPI app created. Run: uvicorn src.app:app --reload
```

That structured trace is the OpenCode-style agent loop running fully on your machine.
