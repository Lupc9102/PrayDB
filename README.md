### Say hello to
# PrayDB
## The only database engine based on gambling and faith.

Why waste time building **actual** database engines, setting up strict data types or writing schemas?
AI can already write your code, emails, breakup messages and [turn communist](https://www.wired.me/story/overworked-ai-agents-turn-marxist-researchers-find), its about time to also let it ~~manage~~ become our databases.
**PrayDB** is a next-gen concept that completely breaks the preconceptions of what data storage should be like from a moral point of view by replacing any kind of logic with high-stakes algorithmic luck (GAMBLING BABYYYY)

Instead of trusting hardware, PrayDB drops your entire transactional integrity to statistical probability, letting you gamble your prod data on *every* *single* *API request.*

### The revolutionary ACID Model
**A** — All on red  
**C** — Crying in the server room  
**I** — Inflation (huge token costs)  
**D** — Despair

## Core Architecture

### Gacha-driven Queries
Traditional query scans are inefficient and boring. PrayDB fixes that by processing *get* requests by wasting Primogems on a random banner and praying it lands on a 5-star character.

---

## Actual Architecture

Jokes aside, here's what this repo actually does.

PrayDB is a Python + JS database where **writes go through an AI model (by chunking)** and **reads go through an AI model (the whole file)**. Every time you write or query your data, a model processes it — it's like having an LLM as your database engine and storage driver.

### How it works

```
            ┌─────────────────────┐
            │  ~/.praydb/db.json  │  ← one file, all data
            │  {                  │
            │    "users": [...],  │
            │    "config": {...}, │
            │    "anything": "goes" │
            │  }                  │
            └────────┬────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
    write (AI chunk)      read (AI full)
    set, delete,          get, dump,
    insert, update        all, search
```

- **Writes** — send only the relevant chunk (e.g., table list or specific key) to the AI, let it perform the edit/insert/update/delete, and write back. Medium API cost.
- **Reads** — send the entire JSON to an OpenRouter model. The model reads it and returns what you asked for. High API cost.

### Install

```bash
cd praydb
python3 -m pip install -e .
export OPENROUTER_API_KEY="sk-or-..."
```

### CLI

```bash
praydb set timezone "GMT+3"
praydb set vibe '{"ui": "squared", "chaos": "low"}'
praydb get timezone
praydb dump
praydb delete vibe
praydb reset
praydb doctor
```

### Python API

```python
from praydb import PrayDB, Query, Condition

db = PrayDB(api_key="sk-or-...", model="openai/gpt-4o-mini")

# Writes are local — no AI
db.set("timezone", "GMT+3")
db.delete("old-key")

# Reads go through the AI
print(db.get("timezone"))
print(db.dump())
print(db.keys())

# TinyDB-style document operations (single monolith)
User = Query()
db.insert({"id": "alice", "role": "admin"})
db.update({"role": "owner"}, User.id == "alice")
print(db.search(User.role == "owner"))
```

### API Reference

| Method | Type | Description |
|--------|------|-------------|
| `set(key, value)` | write | Store a value |
| `get(key)` | read (AI) | Retrieve a value |
| `delete(key)` | write | Remove a key |
| `reset()` | write | Wipe everything |
| `dump()` | read (AI) | Return full state |
| `keys()` | local | List top-level keys |
| `insert(doc, table)` | write | Add a document |
| `insert_multiple(docs, table)` | write | Add documents |
| `all(table)` | read (AI) | Get all documents |
| `search(cond, table)` | read (AI) | Find documents |
| `contains(cond, table)` | read (AI) | Check existence |
| `update(doc, cond, table)` | write | Modify documents |
| `remove(cond, table)` | write | Delete documents |
| `upsert(doc, key_field, table)` | write | Insert or update |
| `truncate(table)` | write | Empty a table |
| `count(table)` | local | Count documents |

### Warnings

- Do not store passwords, secrets, or anything that must survive reality.
- The model might lie. That is not a bug. That is the architecture.
- One file means one file. If it corrupts, everything is gone.

### Deployment

- **Docs**: [lupc.xyz/praydb](https://lupc.xyz/praydb)
- **Demo**: [lupc.xyz/praydb-demo](https://lupc.xyz/praydb-demo) — client-side Puter.js demo, `gpt-5.4-nano`
- **Repo**: [github.com/Lupc9102/PrayDB](https://github.com/Lupc9102/PrayDB)
