# Team Security Guide — Stop the Virus Coming Back
**Send this to everyone who works on Legacy_AI (One-AI).**

## What is going wrong?

A malicious task has been found committed inside our own repo, in `.vscode/tasks.json`. It was added in the **Initial commit** (by mohsin-aliDev), so **every clone of this repo has it**, going back to day one.

It's a hidden VS Code/Cursor task that:
- Runs automatically the moment you open the project folder (`"runOn": "folderOpen"`)
- Is hidden from your terminal panel (`"hide": true`, `"reveal": "never"`)
- Tries to execute a "font" file as JavaScript: `node ./public/fonts/fa-solid-400.woff2`

This is the PolinRider pattern — malware disguised as a font/asset file, auto-run by your editor, that then plants more bad files or exfiltrates data whenever you open the project. Because `.vscode/` was never in our `.gitignore`, this spreads to everyone who clones the repo, without any of us running a suspicious installer.

**This is not a maybe — it's already in git history and in your working copy right now.**

## Before you start
- Set aside 1–2 hours
- You need internet
- Message your team lead when done (see last section)
- Do not skip steps

---

## Part 1 — Clean your GitHub account

**Personal access tokens**
- Open https://github.com/settings/tokens
- Delete/revoke every Fine-grained token
- Delete/revoke every Classic token
- Don't create new ones unless your lead tells you to

**SSH keys**
- Open https://github.com/settings/keys
- Delete any key you don't recognize or no longer use
- Not sure what a key is for? Ask before deleting

**OAuth/GitHub Apps**
- Open https://github.com/settings/applications
- Revoke anything you don't actively use, under both sections

## Part 2 — Scan your computer

- Windows Security → Virus & threat protection → Scan options → **Full scan** → remove anything found
- Optional but recommended: Malwarebytes free, full scan, remove threats

**Do not open the Legacy_AI project in Cursor/VS Code until Part 4 is done.**

## Part 3 — Check your editor (Cursor / VS Code)

**Turn off automatic tasks**
- `Ctrl+,` → search `allow automatic tasks` → set **Task: Allow Automatic Tasks** to **off**
- Close the editor completely

**Remove unknown extensions**
- Reopen the editor → Extensions icon
- Uninstall anything you didn't install yourself or don't recognize
- Keep only extensions you actually use (Python, Pylance, GitLens, etc. — only if you installed them)
- Not sure? Uninstall it. You can reinstall later.

**Going forward**
- Don't install extensions someone sends in chat
- Don't install "AI helper" / "productivity" extensions from unknown publishers
- Only install from well-known publishers, with your lead's approval

## Part 4 — Delete your old clone and get a fresh copy

Your existing local copy already has the infected `tasks.json` — treat it as compromised.

**Save uncommitted work first** — copy any files you have changes in to a safe backup folder. Do **not** copy:
- `.venv/`
- `.vscode/` (this is the infected folder — do not carry it over)
- `__pycache__/`, `.pytest_cache/`, `.langgraph_api/`
- any file you didn't create yourself

**Delete the old folder completely**, then clone fresh:
```
cd D:\Development-Work
git clone https://github.com/Allied-Intelligenza/Legacy_AI.git
```

**Install dependencies the safe way** (this project uses `uv`, not npm):
```
cd Legacy_AI
uv sync
```
- Use `uv sync` only — it installs exactly what's pinned in `uv.lock`
- Don't run `uv add <package>` on your own — ask your lead first
- Our approved dependencies are the normal ones in `pyproject.toml` (FastAPI, LangGraph, LangChain, etc.). The virus doesn't hide in these — it hides in local editor config files like `.vscode/tasks.json`.

## Part 5 — Check that your copy is clean

Before writing any new code, verify:

| File | Should look like |
|---|---|
| `.vscode/tasks.json` | Should **not** contain any task with `"runOn": "folderOpen"`, `"hide": true`, or a reference to a `.woff2`/font file being run with `node`. If in doubt, delete the whole `.vscode/tasks.json`. |
| `public/fonts/fa-solid-400.woff2` (or any `.woff2` outside a real fonts/assets folder) | Should **not** exist in the repo root or backend/. |

Open `.gitignore` — confirm `.vscode/` (or at minimum `.vscode/tasks.json`) gets added, so this can't silently reappear from someone else's commit.

**Bad signs — stop and tell your team lead immediately:**
- Any `"runOn": "folderOpen"` task you didn't add
- Any task with `"hide": true` / `"reveal": "never"` you can't explain
- Any file trying to `node`/`python` execute a font, image, or binary-looking asset
- Long or scrambled/unreadable code in any config file

If anything looks wrong: **do not commit or push.** Message your team lead. Your computer may still be infected — go back to Part 2.

## Part 6 — Rules everyone follows from now on

**Git rules**
- Never force-push to any shared branch (`dev-Sufyan`, `dev-local`, `main`, `staging`, etc.)
- Don't push directly to `main`/`staging` — use a pull request
- Before opening a PR, update your branch from the latest base branch:
  ```
  git fetch origin
  git merge origin/main
  ```
- Create new branches from the latest `main`, not from old feature branches
- If you see files you didn't create — especially under `.vscode/` — **do not commit them**

**Daily habit (30 seconds, before every commit)**
- `.vscode/tasks.json` doesn't exist, or has no auto-run tasks
- No stray `.woff2`/font files outside real asset directories
- `git status` doesn't show files you don't recognize

**Computer habits**
- Keep "Allow Automatic Tasks" set to **off**
- Don't install random browser or editor extensions
- Don't open project zip files from email/chat — only clone from GitHub
- Run a full Windows Defender scan at least monthly

## Part 7 — Confirm with your team lead

Send this once done (fill in your name):

```
Hi, I completed the security cleanup.

Name: [Your name]
GitHub username: [Your username]

Done:
- Revoked all personal access tokens
- Checked SSH keys
- Full virus scan completed
- Editor automatic tasks set to off
- Removed unknown extensions
- Deleted old project folder and cloned fresh
- Ran uv sync on the fresh clone
- Verified .vscode/tasks.json is clean / removed

I will follow the git rules going forward.
```

### Quick checklist
- [ ] Revoke all GitHub personal access tokens
- [ ] Check and remove unknown SSH keys
- [ ] Full virus scan on computer
- [ ] Set automatic tasks to off in editor
- [ ] Remove unknown editor extensions
- [ ] Delete old Legacy_AI folder, clone fresh
- [ ] Run `uv sync` in the fresh clone (not manual pip/uv add)
- [ ] Verify `.vscode/tasks.json` has no malicious auto-run task
- [ ] Sent completion message to team lead

## For team leads
- Everyone completes this within 48 hours
- Remove write access from GitHub until confirmed done
- Whoever's clone had the infected `.vscode/tasks.json` running should get priority
- Add `.vscode/` to `.gitignore` repo-wide so this can't recur
- Rotate any deploy/server keys that were ever on a developer laptop
- Consider branch protection rules to block force-pushes (ties into the separate `dev-Sufyan`/`dev-local` force-push incident we're also tracking)

## Common questions

**Is the virus in our Python packages?**
Usually no. Our `pyproject.toml`/`uv.lock` use normal packages. The virus changes local editor config files (like `.vscode/tasks.json`), not `pyproject.toml`. That's why you must use a fresh clone and `uv sync`, not an old infected folder.

**Can I keep my old folder to save time?**
No. Old folders are likely infected. Clone fresh.

**What if I already pushed bad files?**
Tell your team lead right away. Do not try to fix it alone.
