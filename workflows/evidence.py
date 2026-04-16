from collections.abc import Mapping
from typing import Any, Dict, Iterable, List


def build_evidence_cards_from_literature(entries: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    cards = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        source = entry.get("paper_metadata", {})
        if not isinstance(source, Mapping):
            source = {}
        title = source.get("title", "Unknown paper")
        authors = source.get("authors", [])
        date = source.get("publication_date", "not specified")
        machine_info = _normalize_machine_context(entry)
        energy_data = entry.get("energy_data", {})
        kpis = entry.get("kpi_metrics", {})

        cards.extend(_cards_from_mapping(
            energy_data,
            title=title,
            authors=authors,
            date=date,
            category="energy_data",
            machine_context=machine_info,
        ))
        cards.extend(_cards_from_mapping(
            kpis,
            title=title,
            authors=authors,
            date=date,
            category="kpi_metrics",
            machine_context=machine_info,
        ))

    return cards


def select_relevant_evidence_cards(
    audit_results: Mapping[str, Any],
    evidence_cards: Iterable[Mapping[str, Any]],
    limit: int = 8,
) -> List[Dict[str, Any]]:
    material = str(audit_results.get("metadata", {}).get("material", "")).lower()
    machine_name = str(audit_results.get("metadata", {}).get("machine_name", "")).lower()
    scored = []

    for card in evidence_cards:
        haystack = " ".join(str(value).lower() for value in card.values())
        score = 0
        if material and material in haystack:
            score += 3
        if "milling" in machine_name and "milling" in haystack:
            score += 3
        if any(term in haystack for term in ("energy", "power", "efficiency", "specific")):
            score += 1
        if card.get("value") not in (None, "", "not specified", []):
            score += 1
        scored.append((score, card))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [dict(card) for score, card in scored[:limit] if score > 0]


def _cards_from_mapping(
    mapping: Any,
    title: str,
    authors: list[Any],
    date: str,
    category: str,
    machine_context: Mapping[str, Any],
    prefix: str = "",
) -> List[Dict[str, Any]]:
    cards = []
    if not isinstance(mapping, Mapping):
        return cards
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            cards.extend(_cards_from_mapping(
                value,
                title=title,
                authors=authors,
                date=date,
                category=category,
                machine_context=machine_context,
                prefix=path,
            ))
            continue
        if isinstance(value, list):
            if not value:
                continue
            value_text = "; ".join(str(item) for item in value[:5])
        else:
            value_text = value
        if value_text in (None, "", "not specified"):
            continue
        cards.append({
            "source_title": title,
            "source_authors": authors,
            "source_date": date,
            "category": category,
            "claim_key": path,
            "value": value_text,
            "machine_type": machine_context.get("machine_type") or machine_context.get("machine_name", "not specified"),
            "material": machine_context.get("material_processed", "not specified"),
            "confidence": 0.65,
        })
    return cards


def _normalize_machine_context(entry: Mapping[str, Any]) -> Dict[str, Any]:
    machine_info = entry.get("machine_info", {})
    context: Dict[str, Any] = {}

    if isinstance(machine_info, Mapping):
        context.update(machine_info)
    elif isinstance(machine_info, list):
        machine_names = _collect_values(machine_info, ("machine_name", "maschine_name"))
        machine_types = _collect_values(machine_info, ("machine_type", "maschine_type"))
        if machine_names:
            context["machine_name"] = "; ".join(machine_names)
        if machine_types:
            context["machine_type"] = "; ".join(machine_types)

    if "machine_name" not in context and "maschine_name" in context:
        context["machine_name"] = context["maschine_name"]
    if "machine_type" not in context and "maschine_type" in context:
        context["machine_type"] = context["maschine_type"]

    if "material_processed" not in context:
        material = entry.get("material_processed") or entry.get("material")
        if material:
            context["material_processed"] = material

    return context


def _collect_values(items: list[Any], keys: tuple[str, ...]) -> List[str]:
    values: List[str] = []
    seen = set()
    for item in items:
        if not isinstance(item, Mapping):
            continue
        for key in keys:
            value = item.get(key)
            if value in (None, "", "not specified"):
                continue
            value_text = str(value)
            if value_text not in seen:
                seen.add(value_text)
                values.append(value_text)
            break
    return values
