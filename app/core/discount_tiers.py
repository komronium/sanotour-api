from decimal import Decimal

_ZERO = Decimal("0")


def best_tier_discount_percent(
    tiers: list | None, current_year_bookings: int
) -> Decimal:
    """Pick the highest discount percent unlocked by the agent's current booking count."""
    if not tiers:
        return _ZERO
    best = _ZERO
    for tier in tiers:
        try:
            min_bookings = int(tier["min_bookings"])
            discount = Decimal(str(tier["discount_percent"]))
        except (KeyError, TypeError, ValueError):
            continue
        if current_year_bookings >= min_bookings and discount > best:
            best = discount
    return best


def next_tier(tiers: list | None, current_year_bookings: int) -> dict | None:
    """Return the next tier the agent has not yet reached, with bookings_to_unlock."""
    if not tiers:
        return None
    try:
        ordered = sorted(tiers, key=lambda t: int(t["min_bookings"]))
    except (KeyError, TypeError, ValueError):
        return None
    for tier in ordered:
        try:
            min_b = int(tier["min_bookings"])
            pct = Decimal(str(tier["discount_percent"]))
        except (KeyError, TypeError, ValueError):
            continue
        if current_year_bookings < min_b:
            return {
                "min_bookings": min_b,
                "discount_percent": pct,
                "bookings_to_unlock": min_b - current_year_bookings,
            }
    return None
