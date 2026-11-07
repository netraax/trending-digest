"""Shared, sequential free-tier Groq calls for both digests.

State contains response checkpoints and usage, never API keys or prompts.
Workflows must serialize access to LOG_DIR (no concurrent writers).
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time

import requests

URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]


class SmallerBatchNeeded(RuntimeError):
    pass


def duration(value):
    """Groq reset headers use durations such as 1m2.5s or 250ms."""
    try:
        return max(0, float(value))
    except (TypeError, ValueError):
        units = {"ms": .001, "s": 1, "m": 60, "h": 3600}
        return sum(float(n) * units[u] for n, u in
                   re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", str(value)))


def estimate_tokens(text):
    # Conservative heuristic, NOT an exact tokenizer. 413 still triggers splitting.
    return math.ceil(len(text.encode("utf-8")) / 2) + 128


def response_error(response):
    """Return a short provider error without logging prompts or credentials."""
    try:
        error = response.json().get("error", {})
        detail = error.get("message") or error.get("code") or ""
    except (ValueError, AttributeError, TypeError):
        detail = ""
    if not detail:
        detail = getattr(response, "text", "")
    return " ".join(str(detail).split())[:240]


def request_too_large(response, detail):
    text = (detail or "").lower()
    return (response.status_code == 413
            or "request too large" in text
            or ("requested" in text and "limit" in text
                and any(word in text for word in ("token", "tpm", "context"))))


class GroqClient:
    def __init__(self, api_key, namespace):
        self.api_key = api_key
        self.namespace = namespace
        self.models = [os.environ["GROQ_MODEL"]] if os.getenv("GROQ_MODEL") else MODELS
        self.path = Path(os.getenv("LOG_DIR", "logs")) / "groq_runtime.json"
        self.token_budget = int(os.getenv("GROQ_DAILY_TOKEN_BUDGET", "180000"))
        self.request_budget = int(os.getenv("GROQ_DAILY_REQUEST_BUDGET", "900"))
        self.request_limit = int(os.getenv("GROQ_REQUEST_TOKEN_LIMIT", "7000"))
        self.wait_budget = float(os.getenv("GROQ_MAX_WAIT_SECONDS", "1800"))
        self.waited = 0
        if self.path.exists():
            # A damaged ledger must not silently reset the free-tier budget.
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.state = {"calls": [], "cache": {}, "next_call_at": 0}
        now = time.time()
        self.state["calls"] = [c for c in self.state["calls"] if c["at"] > now - 86400]
        self.state["cache"] = {k: v for k, v in self.state["cache"].items()
                               if v["at"] > now - 86400}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def wait(self, seconds):
        seconds = max(0, seconds)
        if self.waited + seconds > self.wait_budget:
            raise RuntimeError("Quota Groq indisponible : reprise nécessaire, lots terminés conservés.")
        if seconds:
            print(f"Groq : pause quota de {seconds:.0f}s", flush=True)
        self.waited += seconds
        while seconds > 0:
            part = min(seconds, 30)
            time.sleep(part)
            seconds -= part

    def call(self, prompt, output_tokens, validate, retry_hint=""):
        body_base = {"messages": [{"role": "user", "content": prompt}],
                     "temperature": .3, "max_completion_tokens": output_tokens,
                     "response_format": {"type": "json_object"}}
        identity = json.dumps([self.namespace, self.models, body_base], sort_keys=True, ensure_ascii=False)
        key = hashlib.sha256(identity.encode()).hexdigest()
        cached = self.state["cache"].get(key)
        if cached and validate(cached["data"]):
            print(f"Groq [{self.namespace}] : lot repris du cache", flush=True)
            return cached["data"], cached["model"]
        reserved = estimate_tokens(prompt) + output_tokens
        if reserved > self.request_limit:
            raise SmallerBatchNeeded("Lot au-dessus du budget prudent par requête")
        invalid_seen = False
        for model in self.models:
            last_error = "aucune réponse reçue"
            for attempt in range(5):
                self.wait(self.state["next_call_at"] - time.time())
                now = time.time()
                calls = self.state["calls"] = [c for c in self.state["calls"] if c["at"] > now - 86400]
                if len(calls) >= self.request_budget or sum(c["tokens"] for c in calls) + reserved > self.token_budget:
                    raise RuntimeError("Budget Groq partagé sur 24h atteint ; lots terminés conservés pour reprise.")
                record = {"at": now, "stream": self.namespace, "model": model,
                          "tokens": reserved, "estimated": True}
                calls.append(record)
                # Persist BEFORE sending: a timeout/crash may still consume tokens.
                self.state["next_call_at"] = now + 65
                self.save()
                body = dict(body_base, model=model)
                if invalid_seen and retry_hint:
                    body["messages"] = [{"role": "user", "content": prompt + retry_hint}]
                if model.startswith("openai/gpt-oss"):
                    body["reasoning_effort"] = "low"
                try:
                    response = requests.post(URL, headers={"Authorization": f"Bearer {self.api_key}"},
                                             json=body, timeout=90)
                except (requests.Timeout, requests.ConnectionError) as exc:
                    last_error = type(exc).__name__
                    continue
                detail = response_error(response)
                if request_too_large(response, detail):
                    raise SmallerBatchNeeded(
                        f"Groq refuse la taille de la requête (HTTP {response.status_code}): {detail}"
                    )
                if response.status_code == 429:
                    last_error = f"HTTP 429: {detail or 'quota temporairement indisponible'}"
                    delay = max(65, duration(response.headers.get("retry-after")))
                    for resource in ("tokens", "requests"):
                        remaining = response.headers.get(f"x-ratelimit-remaining-{resource}")
                        if remaining is not None and float(remaining) <= 0:
                            delay = max(delay, duration(response.headers.get(f"x-ratelimit-reset-{resource}")))
                    self.state["next_call_at"] = time.time() + delay
                    self.save()
                    continue
                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}: {detail or 'erreur temporaire du fournisseur'}"
                    continue
                if response.status_code in (400, 404) and "model" in response.text.lower():
                    last_error = f"Modèle {model} indisponible (HTTP {response.status_code}): {detail}"
                    break
                if not response.ok:
                    raise RuntimeError(
                        f"Groq HTTP {response.status_code}: {detail or 'aucun détail fourni'}"
                    )
                payload = response.json()
                usage = payload.get("usage", {})
                if isinstance(usage.get("total_tokens"), int):
                    record.update(tokens=usage["total_tokens"], estimated=False,
                                  prompt_tokens=usage.get("prompt_tokens"),
                                  completion_tokens=usage.get("completion_tokens"))
                self.save()
                choice = payload["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise SmallerBatchNeeded("Réponse tronquée : réduire le lot")
                try:
                    data = json.loads(choice["message"]["content"])
                except (ValueError, TypeError):
                    last_error = "réponse reçue mais JSON illisible"
                    invalid_seen = True
                    continue
                if not validate(data):
                    last_error = "JSON reçu mais réponse hors du schéma attendu"
                    invalid_seen = True
                    continue
                self.state["cache"][key] = {"at": time.time(), "data": data, "model": model}
                self.save()
                print(f"Groq [{self.namespace}] : {record['tokens']} tokens"
                      f"{' (estimation)' if record['estimated'] else ''}, "
                      f"total partagé 24h={sum(c['tokens'] for c in calls)}", flush=True)
                return data, model
            print(f"Groq : {model} a échoué après 5 essais ({last_error}); essai du modèle suivant.",
                  file=sys.stderr, flush=True)
        raise RuntimeError(
            f"Groq indisponible après les modèles configurés. Dernier échec : {last_error}. "
            "Les analyses déjà mises en cache sont conservées."
        )

    def analyze(self, instructions, items, field, *, batch_size=2, output_tokens=2200,
                require_all=False, required_fields=(), row_validator=None, retry_hint=""):
        results, models = [], []

        def process(batch):
            names = {item["name"] for item in batch}

            def valid(data):
                if not isinstance(data, dict) or not isinstance(data.get(field), list):
                    return False
                rows = data[field]
                if not all(isinstance(row, dict) and isinstance(row.get("name"), str)
                           and row["name"] in names
                           and all(isinstance(row.get(k), str) and row[k].strip() for k in required_fields)
                           for row in rows):
                    return False
                returned = [row["name"] for row in rows]
                if row_validator and not all(row_validator(row) for row in rows):
                    return False
                return len(returned) == len(set(returned)) and (not require_all or set(returned) == names)

            try:
                data, model = self.call(instructions + "\n\n" + json.dumps(batch, ensure_ascii=False),
                                        output_tokens, valid, retry_hint=retry_hint)
            except SmallerBatchNeeded:
                if len(batch) == 1:
                    raise
                middle = len(batch) // 2
                process(batch[:middle])
                process(batch[middle:])
                return
            results.extend(data[field])
            models.append(model)

        for start in range(0, len(items), batch_size):
            process(items[start:start + batch_size])
        return results, ",".join(dict.fromkeys(models))
