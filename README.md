# WhatsApp Number Checker

A **multi-threaded** tool to check a list of phone numbers against the WhatsApp
API and separate them into **valid** (exists on WhatsApp) and **invalid** files.

- ⚡ **Concurrent** — multiple worker threads check numbers in parallel
- ✅ One line per number with full details (name, about, face analysis, etc.)
- ⏸ **Resume support** — stop and restart anytime, it picks up where it left off
- 🚦 Smart rate-limiting — respects API limits and backs off on 429 errors
- 📥 Accepts a local `.txt` file **or** a URL as input

---

## 📦 Setup (step by step)

### 1. Install Python

If you don't have Python yet:

- **Windows**: Go to https://www.python.org/downloads/ → click **Download Python 3.x**
  - ⚠️ During install, **check the box** that says **"Add Python to PATH"**
- **Mac**: `brew install python3` or download from the link above.

To verify, open a terminal and type:

```
python --version
```

You should see something like `Python 3.10.x` or higher.

### 2. Download this folder

Copy the entire `wa-checker` folder to your computer. Inside you should see:

```
wa-checker/
├── check.py              ← main script you run
├── config.ini            ← your settings (API key goes here)
├── requirements.txt      ← Python dependencies
├── api_client.py
├── config_loader.py
├── formatter.py
├── number_loader.py
├── progress_tracker.py
└── README.md             ← this file
```

### 3. Install dependencies

Open a terminal **inside the `wa-checker` folder** and run:

```
pip install -r requirements.txt
```

### 4. Set your API key

Open **`config.ini`** in any text editor (Notepad, VS Code, etc.) and replace
`YOUR_API_KEY_HERE` with your real API key:

```ini
[api]
api_key = abc123-your-real-key-here
```

### 5. Prepare your phone numbers

Create a file called **`numbers.txt`** in the same folder with one phone number
per line (international format):

```
+96891234567
+96897654321
+14155551234
```

Or point to a URL in `config.ini`:

```ini
[files]
input_file = https://example.com/my-numbers.txt
```

---

## 🚀 Running

```
python check.py
```

That's it! You will see a live progress bar:

```
  [██████████░░░░░░░░░░░░░░░░░░░░] 33.2%  332/1000  ✓ +96891234567  (3.8 req/s · ETA 2.9m · 10w)
```

### CLI options

```
python check.py                   # normal run (uses config.ini)
python check.py --reset           # wipe progress and start fresh
python check.py --config my.ini   # use a different config file
python check.py --workers 20      # override worker count from CLI
```

### Output files

After it finishes (or when you stop it), you'll find:

| File                  | Content                                                  |
| --------------------- | -------------------------------------------------------- |
| `results/valid.txt`   | Numbers on WhatsApp, one per line with full details      |
| `results/invalid.txt` | Numbers NOT on WhatsApp                                  |

**Valid line format** (same as the server export):

```
+96891234567 | name: Ahmed | about: Hello | pic: yes | img: https://whatsapp-db.checkleaked.com/96891234567.jpg | added: 2026-03-15 10:22:00 | face: Young man smiling | tags: person, smile | people: [male/age 20-25]
```

---

## ⏸ Stopping and Resuming

- Press **Ctrl+C** once to stop gracefully.
- Run `python check.py` again and it will **resume** from where it stopped.
- Progress is saved in `results/.progress.json`.

To **start completely fresh** (wipe all progress and results):

```
python check.py --reset
```

---

## ⚙️ Configuration

All settings are in **`config.ini`**:

| Setting               | Default | Description                                     |
| --------------------- | ------- | ----------------------------------------------- |
| `api_key`             | —       | **Required.** Your API key.                     |
| `base_url`            | `https://whatsapp-proxy.checkleaked.cc` | API endpoint       |
| `requests_per_second`  | `3`     | How fast to check (2–4 recommended)             |
| `workers`              | `10`    | Concurrent worker threads (see below)           |
| `max_retries`          | `5`     | Retries per number on errors                    |
| `backoff_start`        | `2.0`   | Initial wait (seconds) after a 429 error        |
| `input_file`           | `numbers.txt` | Local file or URL with phone numbers       |
| `valid_output`         | `results/valid.txt` | Where valid numbers are saved          |
| `invalid_output`       | `results/invalid.txt` | Where invalid numbers are saved      |

### Tuning `workers`

The rate limiter enforces the global `requests_per_second` cap across all
threads. Workers just let multiple HTTP requests be **in-flight** at the same
time so network latency doesn't waste your quota.

Rule of thumb: **workers ≈ requests_per_second × average_latency_seconds**.

| Scenario | `requests_per_second` | `workers` |
|----------|----------------------|-----------|
| Default  | 4                    | 10        |
| Fast API | 4                    | 8         |
| Slow API (~3 s) | 4             | 15        |

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| `❌ Config file not found` | Make sure `config.ini` exists in the same folder |
| `❌ API key is missing` | Open `config.ini` and set your real API key |
| `❌ Input file not found` | Create `numbers.txt` or set the correct path/URL in config |
| Script is slow | Increase `workers` in config.ini (default 10). The rate limiter still caps total RPS. |
| `ModuleNotFoundError: requests` | Run `pip install -r requirements.txt` |
