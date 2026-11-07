"""Load a validated profile and retain every section in a bounded prompt."""
import json
import os
from pathlib import Path

import yaml


def load_profile():
    path = Path(os.getenv("PROFILE_PATH", str(Path(__file__).with_name("profile.yml"))))
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Profil indisponible ou invalide : {path.name}") from exc
    required = ("builder", "technical_mastery", "strategic_focus", "monetization_targets")
    if not isinstance(data, dict) or any(not isinstance(data.get(k), dict) or not data[k] for k in required):
        raise ValueError("Profil incomplet : builder, technical_mastery, strategic_focus et monetization_targets requis")
    profile_context(data)  # Fail before GitHub/Groq calls when the profile cannot fit.
    return data


def profile_context(profile, budget=2400):
    def compact(value, cap):
        if isinstance(value, dict):
            return {str(k): compact(v, cap) for k, v in value.items()}
        if isinstance(value, list):
            return [compact(v, cap) for v in value]
        if isinstance(value, str):
            raw = value.encode("utf-8")
            return value if len(raw) <= cap else raw[:cap].decode("utf-8", errors="ignore") + "…"
        return value

    for cap in (200, 150, 100, 75, 50, 30):
        text = json.dumps(compact(profile, cap), ensure_ascii=False, separators=(",", ":"))
        if len(text.encode("utf-8")) <= budget:
            return text
    raise ValueError("Profil trop volumineux : simplifier les rubriques sans supprimer leurs clés")
