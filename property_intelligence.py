"""Pure, evidence-aware property intelligence calculations.

The module deliberately separates observed facts from estimates.  A missing fact is
reported as ``UNKNOWN`` and optionality never implies legal zoning/permit approval.
"""
from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any, Iterable
from urllib.parse import urlsplit

UNKNOWN = "UNKNOWN"

EVIDENCE_RANK = {
    "official": 4,
    "public_record": 4,
    "broker": 3,
    "listing": 3,
    "marketplace": 2,
    "secondary": 2,
    "inferred": 1,
    "unknown": 0,
}


def _number(value: Any) -> float | None:
    if value is None or value == UNKNOWN or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_evidence(items: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
    """Choose the highest-quality assertion while preserving disagreements."""
    valid = [dict(x) for x in (items or []) if x.get("value") not in (None, "", UNKNOWN)]
    if not valid:
        return {"value": UNKNOWN, "source": UNKNOWN, "source_type": UNKNOWN,
                "has_conflict": False, "alternatives": []}
    valid.sort(key=lambda x: EVIDENCE_RANK.get(str(x.get("source_type", "unknown")).lower(), 0), reverse=True)
    chosen = valid[0]
    alternatives = [x for x in valid[1:] if x.get("value") != chosen.get("value")]
    return {"value": chosen["value"], "source": chosen.get("source", UNKNOWN),
            "source_type": chosen.get("source_type", UNKNOWN),
            "has_conflict": bool(alternatives), "alternatives": alternatives}


def grade_evidence(items: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
    valid = [x for x in (items or []) if x.get("value") not in (None, "", UNKNOWN)]
    if not valid:
        return {"grade": "UNKNOWN", "score": 0, "reason": "No verifiable evidence supplied"}
    ranks = [EVIDENCE_RANK.get(str(x.get("source_type", "unknown")).lower(), 0) for x in valid]
    distinct = len({(x.get("field"), str(x.get("value"))) for x in valid})
    score = min(100, round(max(ranks) * 18 + min(distinct, 4) * 7))
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"
    return {"grade": grade, "score": score, "reason": f"{len(valid)} assertions; best source rank {max(ranks)}/4"}


def detect_data_conflicts(items: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Surface contradictory assertions by field without discarding any source."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for assertion in items or []:
        field = assertion.get("field")
        if field and assertion.get("value") not in (None, "", UNKNOWN):
            grouped.setdefault(str(field), []).append(dict(assertion))
    conflicts = []
    for field, assertions in grouped.items():
        values = {str(x["value"]) for x in assertions}
        if len(values) > 1:
            resolution = resolve_evidence(assertions)
            conflicts.append({"field": field, "selected_value": resolution["value"],
                              "selected_source": resolution["source"],
                              "assertions": assertions, "status": "REVIEW"})
    return conflicts


def detect_changes(history: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    observations = sorted(history or [], key=lambda x: _date(x.get("observed_at")) or datetime.min)
    events: list[dict[str, Any]] = []
    pressure_words = ("cash only", "as-is", "as is", "must sell", "motivated", "seller concession")
    for previous, current in zip(observations, observations[1:]):
        old_price, new_price = _number(previous.get("price")), _number(current.get("price"))
        at = current.get("observed_at", UNKNOWN)
        if old_price and new_price and new_price < old_price:
            events.append({"type": "price_reduction", "observed_at": at,
                           "amount": round(old_price - new_price),
                           "percent": round((old_price - new_price) / old_price * 100, 2)})
        old_status = str(previous.get("listing_status", "")).lower()
        new_status = str(current.get("listing_status", "")).lower()
        if old_status in {"pending", "contingent", "under contract"} and new_status == "active":
            events.append({"type": "back_on_market", "observed_at": at})
        old_desc, new_desc = str(previous.get("description", "")).lower(), str(current.get("description", "")).lower()
        added = [word for word in pressure_words if word in new_desc and word not in old_desc]
        if added:
            events.append({"type": "motivation_language_added", "observed_at": at, "terms": added})
        if previous.get("broker") and current.get("broker") and previous["broker"] != current["broker"]:
            events.append({"type": "broker_changed", "observed_at": at})
    return events


def seller_pressure(history: list[dict[str, Any]] | None, events: list[dict[str, Any]]) -> dict[str, Any]:
    observations = sorted(history or [], key=lambda x: _date(x.get("observed_at")) or datetime.min)
    prices = [_number(x.get("price")) for x in observations]
    prices = [x for x in prices if x is not None and x > 0]
    total_drop = ((prices[0] - prices[-1]) / prices[0] * 100) if len(prices) > 1 else 0
    reductions = sum(e["type"] == "price_reduction" for e in events)
    days = 0
    if len(observations) > 1:
        first, last = _date(observations[0].get("observed_at")), _date(observations[-1].get("observed_at"))
        days = max(1, (last - first).days) if first and last else 0
    pace = reductions / max(days / 30, 1) if days else 0
    score = max(0, min(100, round(total_drop * 2.2 + reductions * 9 + pace * 8
                           + sum(e["type"] == "back_on_market" for e in events) * 18
                           + sum(e["type"] == "motivation_language_added" for e in events) * 12)))
    return {"score": score, "total_price_drop_percent": round(total_drop, 2),
            "reductions": reductions, "observation_days": days,
            "reduction_pace_per_30_days": round(pace, 2)}


def hidden_optionality(prop: dict[str, Any]) -> dict[str, Any]:
    reasons, score = [], 0
    lot = _number(prop.get("lot_sqft"))
    if lot and lot >= 10000:
        score += 25 if lot < 20000 else 35
        reasons.append("oversized lot")
    if prop.get("corner_lot") is True:
        score += 15; reasons.append("corner lot")
    if prop.get("alley_access") is True:
        score += 10; reasons.append("alley access")
    zoning_verified = prop.get("zoning") not in (None, "", UNKNOWN)
    if prop.get("adu_existing") is True:
        score += 20; reasons.append("existing ADU reported")
    return {"score": min(score, 100), "signals": reasons or [UNKNOWN],
            "zoning": prop.get("zoning") if zoning_verified else UNKNOWN,
            "zoning_verified": zoning_verified,
            "warning": "Potential only; verify zoning, permits, utilities, and buildability"}


def micro_market(comps: list[dict[str, Any]] | None, prop: dict[str, Any] | None = None, *,
                 as_of: Any = None, min_comp_count: int = 3, stale_days: int = 180) -> dict[str, Any]:
    prop = prop or {}
    reference = _date(as_of) or datetime.now().astimezone()
    usable, excluded = [], []
    subject_sqft = _number(prop.get("sqft"))
    for comp in comps or []:
        price = _number(comp.get("sold_price"))
        sold_at = _date(comp.get("sold_date"))
        url = str(comp.get("source_url") or "")
        try:
            sourced = urlsplit(url).scheme in {"http", "https"} and bool(urlsplit(url).hostname)
        except ValueError:
            sourced = False
        distance = _number(comp.get("distance_miles"))
        comp_sqft = _number(comp.get("sqft"))
        reasons = []
        if not price or price <= 0: reasons.append("missing sold price")
        if not sold_at: reasons.append("missing sale date")
        elif sold_at.tzinfo is None and reference.tzinfo is not None: sold_at = sold_at.replace(tzinfo=reference.tzinfo)
        if sold_at and sold_at > reference: reasons.append("future-dated sale")
        elif sold_at and (reference - sold_at).days > stale_days: reasons.append("stale sale")
        if not sourced: reasons.append("missing source URL")
        if distance is None or distance < 0 or distance > 2: reasons.append("distance missing or outside 0-2 miles")
        if subject_sqft and (not comp_sqft or abs(comp_sqft - subject_sqft) / subject_sqft > .35):
            reasons.append("size not comparable")
        if prop.get("property_type") and comp.get("property_type") and prop["property_type"] != comp["property_type"]:
            reasons.append("property type mismatch")
        if reasons:
            excluded.append({"comp": comp, "reasons": reasons})
        else:
            usable.append(comp)
    if len(usable) < min_comp_count:
        return {"arv": UNKNOWN, "range_low": UNKNOWN, "range_high": UNKNOWN,
                "comp_count": len(usable), "confidence": "UNKNOWN", "excluded": excluded,
                "reason": f"fewer than {min_comp_count} sourced, recent comparable sales"}
    prices = sorted(_number(c["sold_price"]) for c in usable)
    arv = round(median(prices))
    confidence = "HIGH" if len(prices) >= min_comp_count else "UNKNOWN"
    return {"arv": arv, "range_low": round(prices[0]), "range_high": round(prices[-1]),
            "comp_count": len(prices), "confidence": confidence, "excluded": excluded}


def renovation_spread(price: Any, market: dict[str, Any], rehab: dict[str, Any] | None, *,
                      as_of: Any = None, stale_days: int = 180) -> dict[str, Any]:
    purchase, arv = _number(price), _number(market.get("arv"))
    output = {"low": UNKNOWN, "base": UNKNOWN, "high": UNKNOWN, "provenance": UNKNOWN}
    source_url = str((rehab or {}).get("source_url") or "")
    observed_at = _date((rehab or {}).get("observed_at"))
    try:
        parsed = urlsplit(source_url)
        reference = _date(as_of) or datetime.now().astimezone()
        if observed_at and observed_at.tzinfo is None and reference.tzinfo is not None:
            observed_at = observed_at.replace(tzinfo=reference.tzinfo)
        current = bool(observed_at and observed_at <= reference and
                       (reference - observed_at).days <= stale_days)
        rehab_sourced = parsed.scheme in {"http", "https"} and bool(parsed.hostname) and current
    except ValueError:
        rehab_sourced = False
    if purchase is None or arv is None or not rehab or not rehab_sourced:
        return output
    output["provenance"] = {"source_url": source_url, "observed_at": rehab.get("observed_at")}
    # Low rehab cost yields the high spread, and vice versa.
    for scenario, cost_key in (("high", "low"), ("base", "base"), ("low", "high")):
        cost = _number(rehab.get(cost_key))
        if cost is not None:
            output[scenario] = round(arv - purchase - cost)
    return output


def marketing_inefficiency(prop: dict[str, Any]) -> dict[str, Any]:
    text = f"{prop.get('title', '')} {prop.get('description', '')}".lower()
    signals = []
    checks = (("poor photos", "poor photography"), ("no photos", "missing photography"),
              ("typo", "copy errors"), ("drive by", "limited showing access"),
              ("do not disturb", "limited access"), ("fixer", "condition undersold"))
    for phrase, label in checks:
        if phrase in text:
            signals.append(label)
    if not prop.get("description"):
        signals.append("missing description")
    return {"score": min(100, len(signals) * 18), "signals": signals or [UNKNOWN]}


def counterfactuals(price: Any, market: dict[str, Any], rehab: dict[str, Any] | None) -> list[dict[str, Any]]:
    purchase, arv = _number(price), _number(market.get("arv"))
    scenarios = [("optimistic", 1.05, "low"), ("base", 1.0, "base"), ("pessimistic", .90, "high")]
    rows = []
    for name, arv_factor, rehab_key in scenarios:
        cost = _number((rehab or {}).get(rehab_key))
        profit = round(arv * arv_factor - purchase - cost) if None not in (arv, purchase, cost) else UNKNOWN
        rows.append({"scenario": name, "arv": round(arv * arv_factor) if arv is not None else UNKNOWN,
                     "rehab": round(cost) if cost is not None else UNKNOWN, "estimated_spread": profit})
    return rows


def _score(prop: dict[str, Any], pressure: dict[str, Any], market: dict[str, Any],
           spread: dict[str, Any], evidence: dict[str, Any], optionality: dict[str, Any],
           inefficiency: dict[str, Any]) -> dict[str, Any]:
    base_spread, price = _number(spread.get("base")), _number(prop.get("price"))
    profit = min(35, max(0, round((base_spread / max(price or 1, 1)) * 70))) if base_spread is not None else 0
    distress = min(20, round(pressure["score"] * .20))
    arv = _number(market.get("arv"))
    discount = min(15, max(0, round(((arv - price) / arv) * 30))) if arv and price else 0
    liquidity = min(10, 3 + market["comp_count"] * 2) if market["comp_count"] else 0
    evidence_points = min(10, round(evidence["score"] / 10))
    dealability = min(10, round(optionality["score"] * .04 + inefficiency["score"] * .04 + (2 if price else 0)))
    breakdown = {"profit_spread": profit, "distress_motivation": distress,
                 "discount_equity": discount, "market_liquidity": liquidity,
                 "evidence_quality": evidence_points, "dealability": dealability}
    return {"total": sum(breakdown.values()), **breakdown}


def analyze_property(property_data: dict[str, Any], *, history: list[dict[str, Any]] | None = None,
                     comps: list[dict[str, Any]] | None = None,
                     rehab: dict[str, Any] | None = None,
                     evidence: list[dict[str, Any]] | None = None,
                     conflicts: list[dict[str, Any]] | None = None,
                     as_of: Any = None, min_comp_count: int = 3, stale_days: int = 180) -> dict[str, Any]:
    """Return a deterministic intelligence record without network or database IO."""
    evidence_items = evidence if evidence is not None else property_data.get("evidence", [])
    events = detect_changes(history)
    pressure = seller_pressure(history, events)
    capitulation = {"score": min(100, round(pressure["score"] * .7
                        + sum(e["type"] == "back_on_market" for e in events) * 15
                        + sum(e["type"] == "motivation_language_added" for e in events) * 15)),
                    "status": "HIGH" if pressure["score"] >= 65 else "MEDIUM" if pressure["score"] >= 35 else "LOW"}
    option = hidden_optionality(property_data)
    market = micro_market(comps, property_data, as_of=as_of, min_comp_count=min_comp_count,
                          stale_days=stale_days)
    spread = renovation_spread(property_data.get("price"), market, rehab, as_of=as_of,
                               stale_days=stale_days)
    inefficient = marketing_inefficiency(property_data)
    confidence = grade_evidence(evidence_items)
    conflict_rows = detect_data_conflicts(evidence_items) + list(conflicts or [])
    result = {
        "property_id": property_data.get("id", property_data.get("address", UNKNOWN)),
        "as_of": as_of or UNKNOWN, "change_events": events,
        "opportunity_triggers": [e for e in events if e["type"] in {"price_reduction", "back_on_market", "motivation_language_added", "broker_changed"}],
        "seller_pressure_velocity": pressure, "seller_capitulation_index": capitulation,
        "hidden_optionality": option, "micro_market": market, "renovation_spread": spread,
        "marketing_inefficiency": inefficient,
        "data_conflicts": conflict_rows, "confidence": confidence,
        "counterfactuals": counterfactuals(property_data.get("price"), market,
                                             rehab if spread["provenance"] != UNKNOWN else None),
    }
    result["score_breakdown"] = _score(property_data, pressure, market, spread, confidence, option, inefficient)
    result["opportunity_score"] = result["score_breakdown"]["total"]
    return result


def score_opportunity(property_data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Compatibility entry point for collectors/reporters."""
    return analyze_property(property_data, **kwargs)
