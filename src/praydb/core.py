from __future__ import annotations

import copy
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional


class PrayDBError(RuntimeError):
    pass


class InvalidJSONError(PrayDBError):
    pass


class ModelSaidNo(PrayDBError):
    pass


class Query:
    def __init__(self, path: tuple[Any, ...] = ()) -> None:
        self.path = path

    def __getattr__(self, name: str) -> "Query":
        return Query(self.path + (name,))

    def __getitem__(self, name: Any) -> "Query":
        return Query(self.path + (name,))

    def _value(self, document: Mapping[str, Any]) -> tuple[bool, Any]:
        current: Any = document
        for part in self.path:
            if isinstance(current, Mapping) and part in current:
                current = current[part]
            else:
                return False, None
        return True, current

    def exists(self) -> "Condition":
        return Condition(self.path, "exists")

    def test(self, func: Callable[[Any], bool]) -> "Condition":
        return Condition(self.path, "test", func)

    def __eq__(self, other: Any) -> "Condition":
        return Condition(self.path, "==", other)

    def __ne__(self, other: Any) -> "Condition":
        return Condition(self.path, "!=", other)

    def __lt__(self, other: Any) -> "Condition":
        return Condition(self.path, "<", other)

    def __le__(self, other: Any) -> "Condition":
        return Condition(self.path, "<=", other)

    def __gt__(self, other: Any) -> "Condition":
        return Condition(self.path, ">", other)

    def __ge__(self, other: Any) -> "Condition":
        return Condition(self.path, ">=", other)

    def __and__(self, other: "Condition") -> "Condition":
        return AndCondition(self.exists(), other)

    def __or__(self, other: "Condition") -> "Condition":
        return OrCondition(self.exists(), other)

    def __invert__(self) -> "Condition":
        return NotCondition(self.exists())


class Condition:
    def __init__(self, path: tuple[Any, ...], op: str, expected: Any = None) -> None:
        self.path = path
        self.op = op
        self.expected = expected

    def matches(self, document: Mapping[str, Any]) -> bool:
        found, value = Query(self.path)._value(document)
        if self.op == "exists":
            return found
        if not found:
            return False
        if self.op == "test":
            return bool(self.expected(value))
        if self.op == "==":
            return value == self.expected
        if self.op == "!=":
            return value != self.expected
        try:
            if self.op == "<":
                return value < self.expected
            if self.op == "<=":
                return value <= self.expected
            if self.op == ">":
                return value > self.expected
            if self.op == ">=":
                return value >= self.expected
        except TypeError:
            return False
        return False

    def __and__(self, other: "Condition") -> "Condition":
        return AndCondition(self, other)

    def __or__(self, other: "Condition") -> "Condition":
        return OrCondition(self, other)

    def __invert__(self) -> "Condition":
        return NotCondition(self)


class AndCondition(Condition):
    def __init__(self, left: Condition, right: Condition) -> None:
        super().__init__((), "and")
        self.left = left
        self.right = right

    def matches(self, document: Mapping[str, Any]) -> bool:
        return self.left.matches(document) and self.right.matches(document)


class OrCondition(Condition):
    def __init__(self, left: Condition, right: Condition) -> None:
        super().__init__((), "or")
        self.left = left
        self.right = right

    def matches(self, document: Mapping[str, Any]) -> bool:
        return self.left.matches(document) or self.right.matches(document)


class NotCondition(Condition):
    def __init__(self, inner: Condition) -> None:
        super().__init__((), "not")
        self.inner = inner

    def matches(self, document: Mapping[str, Any]) -> bool:
        return not self.inner.matches(document)


class PrayDB:
    READ_PROMPT = """You are PrayDB, a read-only database. You look at the current state and answer questions about it.

Current state:
```json
{state_json}
```

Request: {operation}

Rules:
- Return ONLY a JSON object with a single key "result" containing the answer.
- For "GET" with a key: result is the value at that key (or null if not found).
- For "DUMP": result is the full state object.
- For "ALL" with a table name: result is the array of documents in that table.
- For "GET_DOC" with a doc_id: result is the document with that _id (or null).
- For "SEARCH" with a condition: result is an array of matching documents.
- For "CONTAINS" with a condition: result is true or false.

Read only. Never modify state. Valid JSON only."""

    WRITE_PROMPT = """You are PrayDB, a database writer. Your job is to modify a specific chunk of the database state.

Chunk path: {chunk_path}
Current chunk value:
```json
{chunk_json}
```

Request: {operation}
Details: {details}

Rules:
- Return ONLY a JSON object with keys "result" and optionally "meta".
- "result" must contain the modified/new value for this chunk.
- Do NOT return the entire database state, only the modified chunk value.
- If the operation is "INSERT", return the updated list of documents under "result". Ensure the new document has a unique integer "_id" (if other documents have integer "_id"s, make it max(ids) + 1, otherwise 1). Under "meta", return a dictionary/object containing the assigned "_id" as "inserted_id".
- If the operation is "UPDATE", return the updated list of documents under "result". Under "meta", return a dictionary containing "updated_count" (integer).
- If the operation is "REMOVE", return the updated list of documents under "result". Under "meta", return a dictionary containing "removed_count" (integer).
- If the operation is "UPSERT", return the updated list of documents under "result". Ensure the document has a unique integer "_id" (if newly inserted). Under "meta", return a dictionary containing "upserted_id" (integer "_id" of the document).
- If the operation is "SET", return the new value for the key under "result".
- If the operation is "DELETE", return null under "result".
- If the operation is "TRUNCATE", return an empty list `[]` under "result".
- If the operation is "RESET", return an empty object `{{}}` under "result".

Valid JSON only. Never return explanations or markdown other than the JSON object."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-5.4-nano",
        file: Optional[str] = None,
        base_url: str = "https://ai.hackclub.com/proxy/v1",
        timeout: int = 30,
        retries: int = 3,
        temperature: float = 0,
        max_tokens: int = 2048,
    ) -> None:
        self.api_key = api_key or os.environ.get("HACKCLUB_API_KEY")
        if not self.api_key:
            raise PrayDBError("Pass api_key= or set HACKCLUB_API_KEY.")
        self.model = model
        self.file = Path(file).expanduser() if file else None
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.last_raw_response: Optional[str] = None
        self.last_prompt: Optional[str] = None
        self.state: Dict[str, Any] = {}

        if self.file and self.file.exists():
            raw = self.file.read_text(encoding="utf-8")
            if raw.strip():
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        self.state = parsed
                except json.JSONDecodeError:
                    pass

    def _save(self) -> None:
        if not self.file:
            return
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(self.file.suffix + ".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/lupc9102/PrayDB",
            "X-Title": "PrayDB",
        }

    def _request_json(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ModelSaidNo(f"AI returned non-object JSON: {type(parsed).__name__}")
                if "error" in parsed:
                    raise ModelSaidNo(f"AI returned an error: {parsed['error']}")
                return parsed
            except ModelSaidNo:
                raise
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                time.sleep(0.5 * attempt)
        raise PrayDBError(f"Model request failed after {self.retries} attempt(s): {last_error}")

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        stripped = text.strip()
        in_string = False
        escape = False
        start = -1
        for idx, char in enumerate(stripped):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                start = idx
                break
        if start == -1:
            raise InvalidJSONError("Model did not return a JSON object.")
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(stripped)):
            char = stripped[idx]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : idx + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError as exc:
                        raise InvalidJSONError(f"Model returned malformed JSON: {exc}") from exc
                    if not isinstance(parsed, dict):
                        raise InvalidJSONError("Model returned JSON, but not an object.")
                    return parsed
        raise InvalidJSONError("Model returned an unclosed JSON object.")

    def _read(self, operation: str, **kwargs: Any) -> Any:
        state_json = json.dumps(dict(self.state), indent=2, sort_keys=True, ensure_ascii=False)
        parts = [f"{k}={v}" for k, v in kwargs.items()]
        op_desc = f"{operation}({', '.join(parts)})" if parts else operation
        prompt = self.READ_PROMPT.format(state_json=state_json, operation=op_desc)
        self.last_prompt = prompt
        messages = [
            {"role": "system", "content": "You are PrayDB. Read-only JSON database."},
            {"role": "user", "content": prompt},
        ]
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        result = self._request_json(payload)
        choices = result.get("choices") or []
        if not choices:
            raise ModelSaidNo("AI returned no choices.")
        content = choices[0].get("message", {}).get("content", "")
        self.last_raw_response = content
        parsed = self._extract_json_object(content)
        return parsed.get("result")

    def _write(self, operation: str, chunk_path: List[str], current_chunk: Any, details: str) -> Dict[str, Any]:
        chunk_json = json.dumps(current_chunk, indent=2, sort_keys=True, ensure_ascii=False)
        path_str = " -> ".join(chunk_path) if chunk_path else "root"
        prompt = self.WRITE_PROMPT.format(
            chunk_path=path_str,
            chunk_json=chunk_json,
            operation=operation,
            details=details,
        )
        self.last_prompt = prompt
        messages = [
            {"role": "system", "content": "You are PrayDB. Database writer. You modify a chunk of the state and return it as JSON."},
            {"role": "user", "content": prompt},
        ]
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        result = self._request_json(payload)
        choices = result.get("choices") or []
        if not choices:
            raise ModelSaidNo("AI returned no choices.")
        content = choices[0].get("message", {}).get("content", "")
        self.last_raw_response = content
        parsed = self._extract_json_object(content)
        return parsed

    def set(self, key: str, value: Any) -> Dict[str, Any]:
        if not isinstance(key, str) or not key:
            raise PrayDBError("Key must be a non-empty string.")
        try:
            json.dumps(value)
        except TypeError as exc:
            raise PrayDBError("Value must be JSON-serializable.") from exc
        
        current = self.state.get(key)
        response = self._write(
            operation="SET",
            chunk_path=[key],
            current_chunk=current,
            details=f"Set value of key '{key}' to: {json.dumps(value, ensure_ascii=False)}"
        )
        self.state[key] = response.get("result")
        self._save()
        return copy.deepcopy(self.state)

    def get(self, key: Optional[str] = None) -> Any:
        return self._read("GET", key=key)

    def delete(self, key: str) -> Dict[str, Any]:
        if key not in self.state:
            return copy.deepcopy(self.state)
        
        current = self.state.get(key)
        self._write(
            operation="DELETE",
            chunk_path=[key],
            current_chunk=current,
            details=f"Delete the key '{key}' and its associated value."
        )
        if key in self.state:
            del self.state[key]
        self._save()
        return copy.deepcopy(self.state)

    def reset(self) -> Dict[str, Any]:
        self._write(
            operation="RESET",
            chunk_path=[],
            current_chunk=self.state,
            details="Wipe everything. Reset the database state to an empty object."
        )
        self.state = {}
        self._save()
        return copy.deepcopy(self.state)

    def dump(self) -> Any:
        return self._read("DUMP")

    def keys(self) -> List[str]:
        return list(self.state.keys())

    def close(self) -> None:
        self._save()

    def insert(self, document: Mapping[str, Any], table: str = "default") -> int:
        if not isinstance(document, Mapping):
            raise PrayDBError("insert() expects a JSON object.")
        try:
            json.dumps(document)
        except TypeError as exc:
            raise PrayDBError("Document must be JSON-serializable.") from exc
        
        tables = self.state.setdefault("tables", {})
        docs = tables.setdefault(table, [])
        
        response = self._write(
            operation="INSERT",
            chunk_path=["tables", table],
            current_chunk=docs,
            details=f"Insert the following document into the table list: {json.dumps(document, ensure_ascii=False)}. Assign it a unique integer '_id' by incrementing the max '_id' present in the list, or starting at 1 if list is empty."
        )
        
        new_docs = response.get("result")
        if not isinstance(new_docs, list):
            raise PrayDBError("AI did not return a list for the updated table.")
        
        tables[table] = new_docs
        self._save()
        
        meta = response.get("meta") or {}
        inserted_id = meta.get("inserted_id") or meta.get("_id")
        
        if inserted_id is None:
            if new_docs:
                inserted_id = new_docs[-1].get("_id")
        
        if inserted_id is None:
            raise PrayDBError("AI failed to assign or return a valid '_id'.")
            
        return int(inserted_id)

    def insert_multiple(self, documents: Iterable[Mapping[str, Any]], table: str = "default") -> List[int]:
        return [self.insert(doc, table) for doc in documents]

    def all(self, table: str = "default") -> Any:
        return self._read("ALL", table=table)

    @staticmethod
    def _describe_condition(condition: Condition) -> str:
        if isinstance(condition, NotCondition):
            return f"NOT ({PrayDB._describe_condition(condition.inner)})"
        if isinstance(condition, AndCondition):
            return f"({PrayDB._describe_condition(condition.left)} AND {PrayDB._describe_condition(condition.right)})"
        if isinstance(condition, OrCondition):
            return f"({PrayDB._describe_condition(condition.left)} OR {PrayDB._describe_condition(condition.right)})"
        path = ".".join(str(p) for p in condition.path)
        if condition.op == "exists":
            return f"{path} exists"
        if condition.op == "test":
            return f"{path} passes custom test"
        return f"{path} {condition.op} {condition.expected!r}"

    def search(self, condition: Condition, table: str = "default") -> Any:
        return self._read("SEARCH", table=table, condition=PrayDB._describe_condition(condition))

    def contains(self, condition: Condition, table: str = "default") -> Any:
        return self._read("CONTAINS", table=table, condition=PrayDB._describe_condition(condition))

    def remove(self, condition: Condition, table: str = "default") -> int:
        tables = self.state.setdefault("tables", {})
        docs = tables.setdefault(table, [])
        before = len(docs)
        
        cond_desc = PrayDB._describe_condition(condition)
        response = self._write(
            operation="REMOVE",
            chunk_path=["tables", table],
            current_chunk=docs,
            details=f"Remove all documents matching condition: {cond_desc}"
        )
        
        new_docs = response.get("result")
        if not isinstance(new_docs, list):
            raise PrayDBError("AI did not return a list for the updated table.")
        
        tables[table] = new_docs
        self._save()
        
        meta = response.get("meta") or {}
        removed_count = meta.get("removed_count")
        if removed_count is None:
            removed_count = max(0, before - len(new_docs))
            
        return int(removed_count)

    def update(self, document: Mapping[str, Any], condition: Optional[Condition] = None, table: str = "default") -> int:
        if not isinstance(document, Mapping):
            raise PrayDBError("update() expects a JSON object.")
        
        tables = self.state.setdefault("tables", {})
        docs = tables.setdefault(table, [])
        before = len(docs)
        
        changes = dict(document)
        changes.pop("_id", None)
        
        cond_desc = PrayDB._describe_condition(condition) if condition else "All documents"
        response = self._write(
            operation="UPDATE",
            chunk_path=["tables", table],
            current_chunk=docs,
            details=f"Update documents matching condition: {cond_desc} by merging these changes: {json.dumps(changes, ensure_ascii=False)}. Do not modify the '_id' field of the documents."
        )
        
        new_docs = response.get("result")
        if not isinstance(new_docs, list):
            raise PrayDBError("AI did not return a list for the updated table.")
            
        tables[table] = new_docs
        self._save()
        
        meta = response.get("meta") or {}
        updated_count = meta.get("updated_count")
        if updated_count is None:
            if condition is None:
                updated_count = len(new_docs)
            else:
                updated_count = sum(1 for i, doc in enumerate(new_docs) if i < len(docs) and doc != docs[i])
                
        return int(updated_count)

    def upsert(self, document: Mapping[str, Any], key_field: str = "id", table: str = "default") -> int:
        if not isinstance(document, Mapping):
            raise PrayDBError("upsert() expects a JSON object.")
            
        tables = self.state.setdefault("tables", {})
        docs = tables.setdefault(table, [])
        
        response = self._write(
            operation="UPSERT",
            chunk_path=["tables", table],
            current_chunk=docs,
            details=f"Upsert document: {json.dumps(document, ensure_ascii=False)} matching by key_field '{key_field}'. If a document with key_field '{key_field}' equal to '{document.get(key_field)}' exists, update it. Otherwise, insert it and assign it a unique integer '_id'."
        )
        
        new_docs = response.get("result")
        if not isinstance(new_docs, list):
            raise PrayDBError("AI did not return a list for the updated table.")
            
        tables[table] = new_docs
        self._save()
        
        meta = response.get("meta") or {}
        upserted_id = meta.get("upserted_id") or meta.get("_id")
        
        if upserted_id is None:
            for doc in new_docs:
                if doc.get(key_field) == document.get(key_field):
                    upserted_id = doc.get("_id")
                    break
                    
        if upserted_id is None and new_docs:
            upserted_id = new_docs[-1].get("_id")
            
        if upserted_id is None:
            raise PrayDBError("AI failed to assign or return a valid '_id'.")
            
        return int(upserted_id)

    def truncate(self, table: str = "default") -> None:
        tables = self.state.setdefault("tables", {})
        docs = tables.setdefault(table, [])
        
        response = self._write(
            operation="TRUNCATE",
            chunk_path=["tables", table],
            current_chunk=docs,
            details=f"Truncate/empty the table '{table}'."
        )
        
        new_docs = response.get("result")
        if not isinstance(new_docs, list):
            new_docs = []
            
        tables[table] = new_docs
        self._save()

    def count(self, table: str = "default") -> int:
        tables = self.state.setdefault("tables", {})
        return len(tables.get(table, []))

    def doctor(self) -> Dict[str, Any]:
        probe_key = "__praydb_doctor_probe__"
        probe_value = {"status": "praying", "vibe": "structurally unsound but functional"}
        before = copy.deepcopy(self.state)
        try:
            self.set(probe_key, probe_value)
            got = self.get(probe_key)
            self.delete(probe_key)
            ok = isinstance(got, dict) and got.get("status") == "praying"
            return {
                "ok": ok,
                "model": self.model,
                "state_keys": len(self.state),
                "message": "AI read the probe correctly." if ok else "AI lied. As predicted.",
            }
        except Exception as exc:
            self.state = before
            self._save()
            return {
                "ok": False,
                "model": self.model,
                "error": str(exc),
                "message": "Doctor mode hit a wall.",
            }
