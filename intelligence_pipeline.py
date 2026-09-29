"""Database-to-intelligence orchestration with strict provenance and UNKNOWN semantics."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import database
from config import MIN_COMP_COUNT, STALE_DATA_DAYS
from property_intelligence import UNKNOWN, analyze_property

MODEL_VERSION = "1"


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _authority(source_type: str | None) -> str:
    value = (source_type or "").lower()
    if value in {"tax_defaulted", "code_violation", "official", "government", "public_record"}:
        return "official"
    if value in {"listing", "broker", "mls"}:
        return "listing"
    if value in {"marketplace", "fsbo", "auction_notice"}:
        return "marketplace"
    return "secondary"


def _lead_evidence(lead: dict[str, Any], raw: dict[str, Any]) -> list[dict[str, Any]]:
    provided = raw.get("evidence") if isinstance(raw.get("evidence"), list) else []
    evidence = []
    allowed_fields = {"address", "city", "price", "sqft", "lot_sqft", "beds", "baths",
                      "zoning", "unit_count", "property_type", "listing_status", "broker",
                      "permits", "taxes"}
    official_hosts = {"kerncounty.com", "kcttc.co.kern.ca.us", "bakersfieldcity.us"}
    for item in provided:
        if not isinstance(item, dict):
            continue
        assertion = {key: item.get(key) for key in
                     ("field", "value", "source", "source_url", "observed_at")}
        if assertion.get("field") not in allowed_fields:
            continue
        try:
            host = (urlsplit(str(assertion.get("source_url") or "")).hostname or "").lower()
        except ValueError:
            host = ""
        asserted_type = str(item.get("source_type") or "secondary").lower()
        is_official_host = (host.endswith(".gov") or
                            any(host == domain or host.endswith("." + domain)
                                for domain in official_hosts))
        if is_official_host:
            assertion["source_type"] = "official"
        elif asserted_type in {"broker", "listing", "marketplace", "secondary"}:
            assertion["source_type"] = asserted_type
        else:
            assertion["source_type"] = "secondary"
        assertion["asserted_source_type"] = asserted_type
        evidence.append(assertion)
    source_type = _authority(lead.get("source_type"))
    for field in ("address", "city", "price"):
        value = lead.get(field)
        if value not in (None, "", 0, UNKNOWN):
            evidence.append({"field": field, "value": value, "source": lead.get("source") or UNKNOWN,
                             "source_url": lead.get("link") or UNKNOWN,
                             "source_type": source_type, "observed_at": lead.get("updated_at") or UNKNOWN})
    return evidence


def _flatten(lead: dict[str, Any], result: dict[str, Any], opportunity_threshold: int,
             watchlist_threshold: int) -> dict[str, Any]:
    score = result["opportunity_score"]
    confidence = result["confidence"]["grade"]
    economics_supported = (result["micro_market"]["confidence"] == "HIGH" and
                           result["renovation_spread"]["base"] != UNKNOWN)
    if score >= opportunity_threshold and confidence in {"A", "B", "C"} and economics_supported:
        decision = "top"
    elif score >= watchlist_threshold or result["opportunity_triggers"]:
        decision = "watchlist"
    else:
        decision = "rejected"
    missing = []
    if result["micro_market"]["arv"] == UNKNOWN:
        missing.append("ARV UNKNOWN: insufficient supplied comparable sales")
    if result["renovation_spread"]["base"] == UNKNOWN:
        missing.append("renovation spread UNKNOWN: supply verified comps and rehab ranges")
    if result["hidden_optionality"]["zoning"] == UNKNOWN:
        missing.append("zoning/use potential UNKNOWN")
    if result["renovation_spread"]["base"] != UNKNOWN:
        missing.append("rehab figures are supplied assumptions; verify with an inspection and bids")
    rejection = [] if decision != "rejected" else ["insufficient verified evidence or economics for threshold"]
    return {
        "property_id": str(lead.get("id") or UNKNOWN),
        "address": lead.get("address") or UNKNOWN,
        "city": lead.get("city") or UNKNOWN,
        "score": score,
        "confidence_grade": confidence,
        "decision": decision,
        "seller_pressure_velocity": result["seller_pressure_velocity"],
        "seller_capitulation_index": result["seller_capitulation_index"],
        "hidden_optionality_score": result["hidden_optionality"]["score"],
        "renovation_spread": result["renovation_spread"],
        "risks": [result["hidden_optionality"]["warning"]],
        "conflicts": result["data_conflicts"],
        "triggers": result["opportunity_triggers"],
        "limitations": missing,
        "rejection_reasons": rejection,
        "next_action": missing[0] if missing else "Verify title, condition, permits, and current availability",
        "analysis": result,
    }


def analyze_all_properties(*, opportunity_threshold: int = 75,
                           watchlist_threshold: int = 50) -> dict[str, Any]:
    database.init_db()
    leads = [dict(row) for row in database.get_leads(min_score=0, limit=100000)]
    rows: list[dict[str, Any]] = []
    events_created = 0
    new_events: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    analyzed_at = datetime.now(timezone.utc).isoformat()
    for lead in leads:
        try:
            raw = _json_object(lead.get("raw_data"))
            observations = database.get_property_observations(str(lead["id"]))
            history = [dict(item["snapshot"], observed_at=item["observed_at"]) for item in observations]
            result = analyze_property(
                lead,
                history=history,
                comps=raw.get("comps") if isinstance(raw.get("comps"), list) else [],
                rehab=raw.get("rehab") if isinstance(raw.get("rehab"), dict) else None,
                evidence=_lead_evidence(lead, raw),
                conflicts=[],
                as_of=analyzed_at,
                min_comp_count=MIN_COMP_COUNT,
                stale_days=STALE_DATA_DAYS,
            )
            for event in result["change_events"]:
                if database.save_property_event(str(lead["id"]), event["type"], event,
                                                detected_at=event.get("observed_at") if event.get("observed_at") != UNKNOWN else analyzed_at):
                    events_created += 1
                    new_events.append({"property_id": str(lead["id"]), "event_type": event["type"],
                                       "observed_at": event.get("observed_at", analyzed_at),
                                       "old_value": event.get("old_value", UNKNOWN),
                                       "new_value": event.get("new_value", event),
                                       "evidence_ids": event.get("evidence_ids", UNKNOWN)})
            row = _flatten(lead, result, opportunity_threshold, watchlist_threshold)
            database.save_property_analysis(str(lead["id"]), row, analyzed_at=analyzed_at,
                                            model_version=MODEL_VERSION)
            rows.append(row)
        except Exception as exc:
            failures.append({"property_id": str(lead.get("id", UNKNOWN)),
                             "error": f"{type(exc).__name__}: {exc}"})
    return {"processed": len(rows), "events_created": events_created, "new_events": new_events,
            "failures": failures, "analyses": rows}
