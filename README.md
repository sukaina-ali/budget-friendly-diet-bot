# Budget-Friendly AI Diet Buddy (Telegram + Gemini)

A Telegram chatbot that helps adult women (18+) in India and Pakistan plan affordable, balanced meals with familiar foods. It remembers each user's preferences, adapts a 7-day example schedule, tracks one weekly treat meal, and logs every message and Gemini token count in your terminal.

> It is a meal-planning helper, **not** a doctor or dietitian. It never claims to cure or reverse insulin resistance, and the 7-day schedule is an example, not a clinically validated prescription.

## Features
- `/start`, `/help`, `/reset`, `/profile`, `/forgetme` plus normal conversation
- Separate per-user records (profile, chat history, daily meal state, treat meal) in local JSON
- Allergy, vegetarian/vegan and red-meat checks done in code (`validators.py`), not only by the AI
- Meals the bot *suggested* are kept separate from meals the user *ate*
- One treat meal per user per week (Monday-based weeks, timezone configurable)
- Terminal logs: incoming/outgoing messages, input/output/total tokens, duration, status
- Optional cost estimate (only if you configure prices)

## Project structure
```
telegram_bot_starter.py   entry point (Telegram handlers)
config.py                 all settings + secrets loading
gemini_client.py          Gemini API wrapper (async, usage, errors)
diet_assistant.py         main logic + system instruction
storage.py                safe JSON storage
validators.py             safety checks
intents.py                extracts facts the user stated (allergy, diet, meals...)
treat_tracker.py          weekly treat-meal logic
meal_framework.py         the 7-day example schedule (editable by an expert)
logging_utils.py          terminal logging (secrets redacted)
tests/                    unit tests (Gemini is mocked)
```
(Extra files beyond the suggested layout: `intents.py`, `treat_tracker.py`, `meal_framework.py`, `logging_utils.py`, to keep each file small and testable.)

## Requirements
- Python 3.10 or newer (developed and tested on 3.12)
- A Telegram account, and a Google account for the Gemini API

## Installation
**Windows (PowerShell)**
```powershell
cd path\to\budget-friendly-diet-bot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```
If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.

**macOS / Linux**
```bash
cd path/to/budget-friendly-diet-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env.example` is a harmless template that is committed to GitHub. `.env` is **your private copy** with real keys; it is ignored by Git. Edit only `.env`.

## Telegram BotFather setup (Token = `TELEGRAM_BOT_TOKEN`)
1. Open Telegram and search for **BotFather** (the official one has a blue verified tick).
2. Send `/newbot`.
3. Choose a display name (e.g. `Budget Diet Buddy`).
4. Choose a unique username ending in `bot` (e.g. `my_budget_diet_buddy_bot`).
5. BotFather replies with a token like `123456789:AA...`. Copy it.
6. Paste it into `.env` after `TELEGRAM_BOT_TOKEN=` (no quotes, no spaces).
7. Keep it secret. If it leaks, send `/revoke` to BotFather.

## Gemini API setup (Key = `GEMINI_API_KEY`)
This is a **different** credential from the Telegram token.
1. Open Google AI Studio (https://aistudio.google.com) and sign in.
2. Choose **Get API key** and create a key.
3. Check the current free-tier limits, quotas and pricing at https://ai.google.dev/gemini-api/docs/pricing.
4. Paste the key into `.env` after `GEMINI_API_KEY=`.
5. Open https://ai.google.dev/gemini-api/docs/models, pick a low-cost "Flash" or "Flash-Lite" model, and copy its exact model code into `GEMINI_MODEL=`. (Model names change over time; I could not verify which one your account can use, so there is no default. If you see "model unavailable", pick another from that page.)
6. Never commit the key to GitHub.

## Run the bot
```bash
python telegram_bot_starter.py
```
Keep the terminal open: the bot only works while it runs. Open your bot in Telegram, press **Start**, and chat. Press `Ctrl+C` to stop.

## Run the tests
```bash
python -m unittest discover -s tests -v
```
No API keys or internet are needed (Gemini is mocked).

## Telegram testing checklist
- [ ] `/start` shows the short greeting; sending it again keeps your data
- [ ] "Give me today's meal plan" returns breakfast/lunch/dinner
- [ ] "I had paratha and chai for breakfast." gets a friendly reply and lunch/dinner ideas
- [ ] "I'm not in the mood for daal." gives 3-5 alternatives
- [ ] "I don't have chia seeds." suggests a cheap swap
- [ ] "I'm allergic to peanuts." is acknowledged; `/profile` shows it; later plans avoid it
- [ ] "I want vegetarian meals from now on." stops chicken/fish/egg suggestions
- [ ] "I had biryani as my treat meal" then "Can I have another treat meal?" explains it is used until next Monday
- [ ] `/reset` keeps `/profile`; `/forgetme` clears everything
- [ ] The terminal shows INCOMING, OUTGOING and GEMINI USAGE blocks

## Privacy notes
- User messages appear in your terminal, and user data is stored unencrypted in `data/users.json` on your computer. Anyone with access to your computer can read both.
- Logs never include API keys (they are redacted), and the app silences library logs that could contain the Telegram token.
- Never commit `data/users.json` (already git-ignored).

## Token usage and cost
Token counts come from the usage numbers Gemini returns (input, output, total). If a call fails before they are available, the log says `unavailable`. To enable the optional estimate, set `INPUT_PRICE_PER_MILLION`, `OUTPUT_PRICE_PER_MILLION` and `PRICE_CURRENCY` in `.env` using the *current* official prices for your model. Without them the log shows "Cost estimate unavailable until pricing is configured." Estimates can differ from Google's actual bill.

## Safety limits (be honest about these)
Checks in `validators.py` are keyword-based. They catch obvious problems (allergen words, meat for vegetarians, cure claims, exact calories, skipping-meal advice) and trigger a regeneration (max 2 retries) or a safe fallback message. They **cannot guarantee allergy safety** (hidden ingredients, spelling variants, packaged foods). Vegetarian is treated as no meat, fish **or eggs**.

## Troubleshooting
| Problem | Fix |
|---|---|
| "settings are missing or still contain placeholder text" | You edited `.env.example` instead of `.env`, or left placeholders. Fill in `.env`. |
| Telegram rejected the bot token | Re-copy the token from BotFather; no spaces/quotes. |
| Replies say "technical problem (configuration)" and the terminal shows `invalid_key` | Re-create the Gemini key in AI Studio and update `.env`. |
| `model_unavailable` | Change `GEMINI_MODEL` to a model listed on the Gemini models page. |
| `rate_limit` | You hit quota/rate limits. Wait, or check your plan and quotas. |
| `network` / timeout | Check internet/VPN/firewall. |
| `pip install` errors | Activate the venv, upgrade pip (`python -m pip install --upgrade pip`), use Python 3.10+. |
| Bot starts but never replies | Make sure you chat with the bot you created (private chat), and only one copy of the bot is running. |
| Permission error writing data | Check that the `data/` folder is writable, or set `DATA_DIR` in `.env`. |
| Timezone error on Windows | `pip install tzdata` (already in requirements). |

## Screenshots (add your own real ones)
After running the bot, take real screenshots and save them in `screenshots/` with these names. Do not fake them.
1. `screenshots/01-start.png` - the `/start` greeting
2. `screenshots/02-meal-plan.png` - a meal-plan reply
3. `screenshots/03-substitution.png` - a substitution or meal update
4. `screenshots/04-terminal-logs.png` - terminal input/output logs with token usage (hide anything private)

![start](screenshots/01-start.png)
![meal plan](screenshots/02-meal-plan.png)
![substitution](screenshots/03-substitution.png)
![terminal](screenshots/04-terminal-logs.png)

## Publish to GitHub (step by step)

### A. Prepare
1. Run the tests (command above) and the bot; capture the 4 screenshots.
2. Confirm `.env` exists locally but is **not** tracked, and no key appears in any file.

### B. Initialise Git
```bash
cd path/to/budget-friendly-diet-bot
git init
git add .
git status
```
Always read `git status` before committing: it lists exactly what will be uploaded. `.env` and `data/users.json` must **not** appear. If `.env` appears, run `git rm --cached .env`, make sure `.gitignore` contains `.env`, then `git add .` and check again.

### C. Create the repository on GitHub
1. Sign in at github.com and click **New repository**.
2. Name it `budget-friendly-diet-bot` and add a short description.
3. Choose Public or Private as your assignment requires.
4. Do **not** tick "Add a README", ".gitignore" or a license (you already have them locally).
5. Click **Create repository**, then copy the URL shown (HTTPS looks like `https://github.com/YOUR_USERNAME/budget-friendly-diet-bot.git`).

### D. Commit and push
```bash
git commit -m "Initial commit: Budget-Friendly AI Diet Buddy"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```
(If Git asks who you are: `git config --global user.name "Your Name"` and `git config --global user.email "you@example.com"`. For HTTPS login GitHub asks for a Personal Access Token instead of a password, or use GitHub Desktop / `gh auth login`.)

### E. Verify
Open your repository page and check: all `.py` files, `tests/`, `README.md`, `requirements.txt`, `.env.example`, `.gitignore` and screenshots are there; **`.env` is not**; the README renders. Copy the page URL for submission.

### F. Fix common problems
- **remote origin already exists**: `git remote set-url origin YOUR_GITHUB_REPOSITORY_URL`
- **rejected: remote contains work**: `git pull origin main --allow-unrelated-histories`, resolve any conflicts, then `git push -u origin main`
- **Authentication/permission denied**: use a Personal Access Token (GitHub, Settings, Developer settings) or `gh auth login`; check you own the repository.
- **Staged `.env` before committing**: `git rm --cached .env` (the local file stays).
- **Committed or pushed a key**: deleting it in a later commit is **not enough**, the key stays in history. **Revoke/rotate it immediately** (BotFather `/revoke` for Telegram; delete and recreate the Gemini key in AI Studio), then clean the history (e.g. with `git filter-repo`) or recreate the repository. Never paste keys into chat for troubleshooting.

## Final submission checklist
- [ ] Tests pass
- [ ] Bot tested in Telegram; screenshots are real
- [ ] `.env` not on GitHub; no keys anywhere in the repo
- [ ] README renders; repository URL copied
