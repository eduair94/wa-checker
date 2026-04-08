# WhatsApp Number Checker

Check a list of phone numbers to see which ones have WhatsApp accounts.

- ⚡ **Fast** — checks hundreds of numbers per second
- ⏸ **Resumable** — stop anytime, it picks up where you left off
- 🧙 **Easy setup** — just run it and answer 3 questions

---

## � Quick Start (3 steps)

### Step 1 — Install Python (skip if you already have it)

1. Go to **https://python.org/downloads**
2. Click the big **"Download Python"** button
3. Run the installer
   - ⚠️ **IMPORTANT:** Check the box that says **"Add Python to PATH"** before clicking Install

To verify it worked, open a terminal and type:
```
python --version
```
You should see `Python 3.10` or higher.

> **How to open a terminal:**
> - **Windows:** Press `Win + R`, type `cmd`, press Enter
> - **Mac:** Press `Cmd + Space`, type `Terminal`, press Enter

### Step 2 — Prepare your phone numbers

Create a file called **`numbers.txt`** in the same folder as this tool.
Put one phone number per line (with country code):

```
+96891234567
+96897654321
+14155551234
```

### Step 3 — Run it!

Open a terminal **in the folder where you downloaded this tool** and type:

```
python check.py
```

**That's it!** On the first run it will:
1. ✅ Automatically install what it needs
2. ⚙️ Walk you through a quick 3-question setup (API key, file, speed)
3. 🚀 Start checking numbers

You'll see a live progress bar:
```
  [██████████░░░░░░░░░░░░░░░░░░░░] 33.2%  3320/10000  ✓ +96891234567  (42.5 req/s · ETA 2.6m · 200w)
```

---

## 📂 Where are the results?

After it finishes (or when you stop it), you'll find two files:

| File                  | What's inside                                    |
| --------------------- | ------------------------------------------------ |
| `results/valid.txt`   | Numbers that **have** WhatsApp (with details)    |
| `results/invalid.txt` | Numbers that **don't have** WhatsApp             |

---

## ⏸ Stopping and Resuming

- Press **Ctrl+C** to stop. Your progress is saved automatically.
- Just run `python check.py` again and it continues where it left off.
- To **start over from scratch**: `python check.py --reset`

---

## ⚙️ Changing Settings

All settings are in **`config.ini`** (created automatically on first run).
Open it with any text editor (Notepad, VS Code, etc.):

| Setting               | What it does                                            |
| --------------------- | ------------------------------------------------------- |
| `api_key`             | Your API key (required)                                 |
| `input_file`          | Your numbers file or URL (default: `numbers.txt`)       |
| `requests_per_second` | How fast to check (default: `50`)                       |
| `workers`             | How many checks run at the same time (default: `200`)   |

**Speed tips:**
- Start with `50` requests per second
- If it works fine, try `100` or `200`
- If you see lots of errors, lower it back down

To override speed without editing the file:
```
python check.py --workers 300
```

---

## ❓ Common Problems

| Problem | Solution |
|---------|----------|
| `python` is not recognized | Re-install Python and check **"Add to PATH"** |
| Setup wizard asks for API key | Paste the key you received from the API service |
| `Input file not found` | Make sure `numbers.txt` is in the same folder |
| Very slow progress | Increase `requests_per_second` in config.ini |
| Lots of errors/retries | Lower `requests_per_second` — you may be hitting API limits |
