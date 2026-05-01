from datetime import datetime, timezone


def property_score(p):
    score = 0
    now = datetime.now(timezone.utc)

    if p.featured:
        score += 50

    if p.featured_until:
        if p.featured_until.tzinfo is None:
            p.featured_until = p.featured_until.replace(tzinfo=timezone.utc)

        days_left = (p.featured_until - now).days
        if days_left > 0:
            score += min(40, days_left * 5)

    score += (p.views or 0) * 0.4

    if p.location:
        popular_cities = ["lagos", "abuja", "ibadan"]
        if any(city in p.location.lower() for city in popular_cities):
            score += 25

    if p.price and 500000 <= p.price <= 5000000:
        score += 20

    if p.bedrooms in [1, 2, 3]:
        score += 15

    return score