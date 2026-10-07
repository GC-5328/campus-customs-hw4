# Campus Customs — HW 4

A Yale merchandise shop with an AI shopping assistant: React + Vite + TypeScript front end, FastAPI back end, and a PydanticAI agent (`gpt5.6-luna` via Portkey) that answers from the shop's SQLite database.

```
HW 4/
├── backend/
│   ├── main.py            FastAPI app: products, images, auth, chat routes
│   ├── agent.py           PydanticAI agent wiring (prompt file + Portkey model, validators)
│   ├── tools.py           Agent tools: search_products, get_product_info, check_stock
│   ├── models.py          Request / reply / product-card / tool-result types
│   ├── prompts/prompt.md  System prompt (voice, tool use, safety rules)
│   ├── memory.py          Saved chat history, customer profile, page context, password redaction
│   ├── audit.py           Append-only agent audit trail → output/audit_trail.json
│   ├── auth.py, db.py     Password hashing + sessions, SQLite helpers
│   ├── clean_images.py    Makes white-background web copies of the product photos
│   └── test_*.py          Offline + live test suites
├── frontend/              React + Vite + TypeScript site
├── data/                  ← the data pack goes here (not in the repo)
├── output/                harness.md, usability.md, design.md, app_check.html, audit_trail.json
├── AI_prompts.md          Prompt log
├── requirements.txt       Python dependencies for the back end
├── .env.example           Environment variables (placeholders only)
└── .gitignore             Keeps .env, the database, and images out of git
```

## 1. Data pack (not in the repo)

The database and product photos aren't committed. Put the course data pack in `data/` so it looks like this:

```
data/
├── campus_customs.db      SQLite: catalogue, inventory, users, chat_messages
└── products/              the 102 product photos (*.jpg)
```

## 2. Environment

Copy the example file and add your Portkey key. `.env` is git-ignored; it can live in `HW 4/` or any parent folder.

```bash
cp .env.example .env
```

## 3. Back end (FastAPI + agent): http://127.0.0.1:8000

First time only, from `HW 4/`: create the virtual environment (Python 3.12) and install dependencies.

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

First time only, from `HW 4/backend`: make the white-background web copies of the photos (writes `data/products_web/`; the originals aren't changed).

```bash
../.venv/bin/python clean_images.py
```

Run the back end from `HW 4/backend`:

```bash
source ../.venv/bin/activate && uvicorn main:app --reload --port 8000
```

On first start it adds a nullable `page_title` column to `chat_messages` if it's missing. Nothing else in the database changes.

## 4. Front end (React + Vite): http://localhost:5174

From `HW 4/frontend`, first time only:

```bash
npm install
```

Then:

```bash
npm run dev
```

Open http://localhost:5174. Vite forwards `/api` and `/media` to the back end on port 8000. If your back end is on another port, start the front end with `API_PORT=8001 npm run dev`.

**Try it:**
- Log in with the seed test user `test@campuscustoms.yale.edu` / `password`.
- Ask the chat (bottom-right button) "what hoodies do you have?".
- Open a product and ask "do you have this in pink?".

## API

| Endpoint | Returns |
|---|---|
| `GET /api/health` | `{"status": "ok"}` |
| `GET /api/products?q=hoodie` | All products (optional search), each with per-size `inventory` and `total_stock` |
| `GET /api/products/{product_id}` | One product, or 404 |
| `GET /media/products/{file}.jpg` | Product image |
| `POST /api/auth/signup` | Create account `{first_name, last_name, email, password, confirm_password}`, sets session cookie |
| `POST /api/auth/login` | `{email, password}` → user (no hash), sets session cookie |
| `POST /api/auth/logout` | Clears the session cookie |
| `GET /api/auth/me` | Current user, or 401 |
| `POST /api/chat` | `{message, page:{path, results_title}, history}` → `{reply, products:[card], page_title}` (history used for guests only) |
| `GET /api/chat/history` | Logged-in shopper's saved chat (401 for guests) |

## Tests

From `HW 4/backend`:

- **Offline, no model calls:** `../.venv/bin/python test_tools.py`
- **With the back end running** (add a port argument if it isn't on 8000):
  - `../.venv/bin/python test_auth.py`: sign-up and log-in. It creates a test account and saves it to `backend/test_account.json`, which is git-ignored.
  - `../.venv/bin/python test_chat.py`: chat checks against the live model.
  - `../.venv/bin/python bench_chat.py [port] [rounds]`: reply time and length.

## Docs

- `output/harness.md`: the full reference. Database fields, how the app is wired, every model field, the tools, safety rules, audit trail, and specs (model, loop limits, result caps).
- `output/usability.md`: search bar, size stock, out-of-stock fallback, faster replies.
- `output/design.md`: the visual design.
- `output/app_check.html`: manual app checks with screenshots.
