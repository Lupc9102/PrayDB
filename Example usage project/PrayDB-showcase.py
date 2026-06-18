# Interactive Praydb script and (maybe) useful code snippets

import json
import os
import sys

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    from rich.text import Text
    from rich.prompt import Prompt
    from rich.syntax import Syntax
except ImportError:
    print("install rich first with `pip install rich`")
    sys.exit(1)

try:
    sys.path.insert(0, os.path.join(os.path.join(os.path.dirname(__file__), ".PrayDB"), "src"))
    from praydb import PrayDB, Query, Condition
except ImportError:
    print("You sure Praydb is installed?")
    print("or run: cd PrayDB")
    print("pip install -e .")
    sys.exit(1)
console = Console()

BANNER = """
 ██████╗ ██████╗  █████╗ ██╗   ██╗██████╗ ██████╗
 ██╔══██╗██╔══██╗██╔══██╗╚██╗ ██╔╝██╔══██╗██╔══██╗
 ██████╔╝██████╔╝███████║ ╚████╔╝ ██║  ██║██████╔╝
 ██╔═══╝ ██╔══██╗██╔══██║  ╚██╔╝  ██║  ██║██╔══██╗
 ██║     ██║  ██║██║  ██║   ██║   ██████╔╝██████╔╝
 ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═════╝ ╚═════╝
"""
Commands = {
    # Key-value
    "set":              "set <key> <value>          — store a value (write, local)",
    "get":              "get <key>                  — retrieve a value (read, AI)",
    "delete":           "delete <key>               — remove a key (write, local)",
    "keys":             "keys                       — list all top-level keys (local)",
    "dump":             "dump                       — AI summary of full state (read, AI)",
    "reset":            "reset                      — wipe everything (write, local)",
    # Documents
    "insert":           "insert <table> <json>      — add a document",
    "insert_multiple":  "insert_multiple <table> <json_array>  — add multiple docs",
    "all":              "all <table>                — get all docs (read, AI)",
    "search":           "search <table> <field> <op> <value>   — find docs (read, AI)",
    "contains":         "contains <table> <field> <op> <value> — check existence (read, AI)",
    "update":           "update <table> <field> <op> <value> <json>  — modify docs",
    "remove":           "remove <table> <field> <op> <value>   — delete matching docs",
    "upsert":           "upsert <table> <key_field> <json>     — insert or update",
    "truncate":         "truncate <table>           — empty a table",
    "count":            "count <table>              — count docs (local)",
    # Meta
    "doctor":           "doctor                     — run a diagnostic check",
    "state":            "state                      — print raw in-memory state",
    "demo":             "demo                       — run a full auto-demo of all features",
    "help":             "help                       — show this list",
    "quit":             "quit / exit                — goodbye",
}

def print_banner():
    console.print(BANNER, style="bold magenta")
    console.print(
        Panel(
            "[bold]The only database engine based on gambling and faith.[/bold]\n"
            "[dim]Writes: instant local JSON.  Reads: AI-powered prayer.[/dim]",
            border_style="magenta",
        )
    )
def print_help():
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    t.add_column("command", style="bold yellow", no_wrap=True)
    t.add_column("description", style="dim")
    for cmd, desc in Commands.items():
        name, _, explanation = desc.partition(" — ")
        local = "[green](local)[/green]" if "(local)" in explanation else ""
        ai    = "[yellow](AI)[/yellow]"  if "(AI)"    in explanation else ""
        badge = f" {local}{ai}".strip() if (local or ai) else ""
        clean = explanation.replace("(write, local)", "").replace("(read, AI)", "").replace("(local)", "").strip(" ,—")
        t.add_row(cmd, f"{clean}{badge}")
    console.print(t)

def pprint_result(label: str, value, write: bool = False):
    color = "green" if write else "yellow"
    icon  = "✓" if write else "🙏"
    serialized = json.dumps(value, indent=2, ensure_ascii=False) if not isinstance(value, str) else value
    console.print(f"[{color}]{icon} {label}[/{color}]")
    if serialized and serialized != "null":
        console.print(Syntax(serialized, "json", theme="monokai", background_color="default"))

def parse_condition(db_table_docs, field, op, raw_val):
    # Condition for em cli tokens
    Q = Query()
    q = getattr(Q, field)
    try:
        val = json.loads(raw_val)
    except json.JSONDecodeError:
        val = raw_val
    ops = {"==": q == val, "!=": q != val, "<": q < val, "<=": q <= val,
           ">": q > val, ">=": q >= val}
    if op not in ops:
        raise ValueError(f"Unsupported operator: {op}")
    return ops[op]

def run_demo(db: PrayDB):
    """Auto-demo of every PrayDB feature."""
    steps = []

    def step(title, code_str, fn):
        steps.append((title, code_str, fn))

    step("set — store key/value",
         'db.set("app", "PrayDB Demo")\ndb.set("version", 1)\ndb.set("config", {"debug": True, "retries": 3})',
         lambda: (db.set("app", "PrayDB Demo"), db.set("version", 1), db.set("config", {"debug": True, "retries": 3})))

    step("keys — list all top-level keys  (local, free)",
         'db.keys()',
         lambda: db.keys())

    step("get — AI reads a value  🙏",
         'db.get("app")',
         lambda: db.get("app"))

    step("dump — AI summarises full state  🙏",
         'db.dump()',
         lambda: db.dump())

    step("delete — remove a key",
         'db.delete("version")',
         lambda: db.delete("version"))

    step("insert — add documents to a table",
         'db.insert({"name": "Alice", "role": "admin",  "score": 99}, table="users")\n'
         'db.insert({"name": "Bob",   "role": "member", "score": 42}, table="users")\n'
         'db.insert({"name": "Carol", "role": "admin",  "score": 77}, table="users")',
         lambda: (
             db.insert({"name": "Alice", "role": "admin",  "score": 99}, table="users"),
             db.insert({"name": "Bob",   "role": "member", "score": 42}, table="users"),
             db.insert({"name": "Carol", "role": "admin",  "score": 77}, table="users"),
         ))

    step("insert_multiple — batch insert",
         'db.insert_multiple([{"item": "sword", "qty": 1}, {"item": "potion", "qty": 5}], table="inventory")',
         lambda: db.insert_multiple([{"item": "sword", "qty": 1}, {"item": "potion", "qty": 5}], table="inventory"))

    step("count - count docs in table (local,free)",
         'db.count("users")',
         lambda: db.count("users"))

    step("all — get all documents from a table  🙏",
            'db.all("users")',
            lambda: db.all("users"))
    
    User = Query()
    step("search — find documents matching a documents  🙏",
         'User = Query()\ndb.search(User.role == "admin", table="users")',
         lambda: db.search(User.role == "admin", table="users"))
    
    step("contains — AI checks if any doc matches  🙏",
         'db.contains(User.score > 90, table="users")',
         lambda: db.contains(User.score > 90, table="users"))

    step("update — modify matching documents",
         'db.update({"role": "owner"}, User.name == "Alice", table="users")',
         lambda: db.update({"role": "owner"}, User.name == "Alice", table="users"))

    step("upsert — insert-or-update by key field",
         'db.upsert({"name": "Bob", "role": "moderator", "score": 50}, key_field="name", table="users")',
         lambda: db.upsert({"name": "Bob", "role": "moderator", "score": 50}, key_field="name", table="users"))

    step("remove — delete matching documents",
         'db.remove(User.score < 50, table="users")',
         lambda: db.remove(User.score < 50, table="users"))

    step("truncate — empty a whole table",
         'db.truncate("inventory")',
         lambda: db.truncate("inventory"))

    step("reset — wipe everything",
         'db.reset()',
         lambda: db.reset())

    step("doctor — self-diagnostic health check  🙏",
         'db.doctor()',
         lambda: db.doctor())

    console.rule("[bold magenta]PrayDB Demo...[/bold magenta]")
    for i, (title, code, fn) in enumerate(steps,1):
        console.print(f"\n[bold cyan]Step {i}: {title}[/bold cyan]")
        console.print(Syntax(code, "python", theme="monokai", background_color="default"))
        try:
            result = fn()
            if isinstance(result, tuple):
                result = result[-1]  # show last step result if multiple
            is_write = not any(kw in title for kw in ("get", "dump", "all", "search", "contains", "doctor", "count"))
            pprint_result("Result", result, write=is_write)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
        if i < len(steps):
            ans= Prompt.ask("[dim] Press Enter for next step or q to quit (real gamblers never quit)", default="")
            if ans.strip().lower() == "q":
                break
    console.rule("[bold magenta]Demo complete![/bold magenta]")



def repl(db: PrayDB):
    User = Query()
    console.print("\nType [bold cyan]help[/bold cyan] for commands, [bold cyan]demo[/bold cyan] to see everything working  \n")
    while True:
        try:
            raw = Prompt.ask("[bold magenta]praydb[/bold magenta]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            break

        parts = raw.strip().split()
        if not parts:
            continue
        cmd, *args = parts

        try:
            if cmd in ("quit", "exit", "q"):
                console.print("[dim]The model shall pray for you.[/dim]")
                break

            elif cmd == "help":
                print_help()

            elif cmd == "demo":
                run_demo(db)

            elif cmd == "state":
                pprint_result("in-memory state", db.state, write=True)

            elif cmd == "keys":
                pprint_result("keys", db.keys(), write=True)

            elif cmd == "dump":
                pprint_result("dump", db.dump())

            elif cmd == "reset":
                if Prompt.ask("[red]Wipe everything?[/red] [dim](yes/no)[/dim]", default="no").lower() == "yes":
                    pprint_result("reset", db.reset(), write=True)

            elif cmd == "doctor":
                pprint_result("doctor", db.doctor())

            elif cmd == "set":
                if len(args) < 2:
                    console.print("[red]Usage: set <key> <value>[/red]"); continue
                key = args[0]
                raw_val = " ".join(args[1:])
                try:
                    val = json.loads(raw_val)
                except json.JSONDecodeError:
                    val = raw_val
                pprint_result(f'set "{key}"', db.set(key, val), write=True)

            elif cmd == "get":
                if not args:
                    console.print("[red]Usage: get <key>[/red]"); continue
                pprint_result(f'get "{args[0]}"', db.get(args[0]))

            elif cmd == "delete":
                if not args:
                    console.print("[red]Usage: delete <key>[/red]"); continue
                pprint_result(f'delete "{args[0]}"', db.delete(args[0]), write=True)

            elif cmd == "insert":
                if len(args) < 2:
                    console.print("[red]Usage: insert <table> <json>[/red]"); continue
                table = args[0]
                doc = json.loads(" ".join(args[1:]))
                pprint_result(f'insert → "{table}"', db.insert(doc, table=table), write=True)

            elif cmd == "insert_multiple":
                if len(args) < 2:
                    console.print("[red]Usage: insert_multiple <table> <json_array>[/red]"); continue
                table = args[0]
                docs = json.loads(" ".join(args[1:]))
                pprint_result(f'insert_multiple → "{table}"', db.insert_multiple(docs, table=table), write=True)

            elif cmd == "all":
                table = args[0] if args else "default"
                pprint_result(f'all "{table}"', db.all(table=table))

            elif cmd == "count":
                table = args[0] if args else "default"
                pprint_result(f'count "{table}"', db.count(table=table), write=True)

            elif cmd == "truncate":
                table = args[0] if args else "default"
                db.truncate(table=table)
                pprint_result(f'truncate "{table}"', f'Table "{table}" emptied.', write=True)

            elif cmd in ("search", "contains", "remove"):
                # usage: search <table> <field> <op> <value>
                if len(args) < 4:
                    console.print(f"[red]Usage: {cmd} <table> <field> <op> <value>[/red]"); continue
                table, field, op = args[0], args[1], args[2]
                raw_val = " ".join(args[3:])
                cond = parse_condition(None, field, op, raw_val)
                if cmd == "search":
                    pprint_result(f'search "{table}"', db.search(cond, table=table))
                elif cmd == "contains":
                    pprint_result(f'contains "{table}"', db.contains(cond, table=table))
                elif cmd == "remove":
                    pprint_result(f'remove from "{table}"', db.remove(cond, table=table), write=True)

            elif cmd == "update":
                # usage: update <table> <field> <op> <value> <json_patch>
                if len(args) < 5:
                    console.print("[red]Usage: update <table> <field> <op> <value> <json>[/red]"); continue
                table, field, op = args[0], args[1], args[2]
                # last token is the patch JSON; everything between op and patch is the value
                patch_json = args[-1]
                raw_val = " ".join(args[3:-1])
                cond = parse_condition(None, field, op, raw_val)
                patch = json.loads(patch_json)
                pprint_result(f'update "{table}"', db.update(patch, cond, table=table), write=True)

            elif cmd == "upsert":
                # usage: upsert <table> <key_field> <json>
                if len(args) < 3:
                    console.print("[red]Usage: upsert <table> <key_field> <json>[/red]"); continue
                table, key_field = args[0], args[1]
                doc = json.loads(" ".join(args[2:]))
                pprint_result(f'upsert "{table}"', db.upsert(doc, key_field=key_field, table=table), write=True)

            else:
                console.print(f"[red]Unknown command:[/red] {cmd}  (type [cyan]help[/cyan])")

        except json.JSONDecodeError as e:
            console.print(f"[red]JSON parse error:[/red] {e}")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")

def main():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print(Panel(
            "[bold red]OPENROUTER_API_KEY not set.[/bold red]\n\n"
            "Export it first:\n"
            "[cyan]export OPENROUTER_API_KEY=sk-or-...[/cyan]\n\n"
            "Get a key at [link=https://openrouter.ai]openrouter.ai[/link] (free tier available).",
            title="Missing API Key",
            border_style="red",
        ))
        sys.exit(1)

    print_banner()
    db = PrayDB(
        api_key=api_key,
        model="openai/gpt-5.4-nano", # cheapest bullsht that might not hallucinate
    )

    console.print(f"[dim]model:[/dim] [cyan]{db.model}[/cyan]   "
                  f"[dim]storage:[/dim] [cyan]in-memory[/cyan]   "
                  f"[dim]ACID:[/dim] [magenta]All on red / Crying / Inflation / Despair[/magenta]")

    repl(db)


if __name__ == "__main__":
    main()