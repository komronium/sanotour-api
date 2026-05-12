from datetime import date, timedelta


def date_range(start: date, end: date) -> list[date]:
    """Inclusive start, exclusive end — same semantics as check_in/check_out."""
    return [start + timedelta(days=i) for i in range((end - start).days)]
