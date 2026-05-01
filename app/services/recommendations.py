from app.models import Property, UserActivity
from app.services.properties import property_score


def get_recommendations(user_id):

    # safety check
    if hasattr(user_id, "id"):
        user_id = user_id.id
    activities = UserActivity.query.filter_by(user_id=user_id).all()

    if not activities:
        return Property.query.order_by(Property.featured.desc()).limit(8).all()

    city_count = {}
    prices = []
    bedrooms = []

    for a in activities:
        city_count[a.city] = city_count.get(a.city, 0) + 1
        if a.price:
            prices.append(a.price)
        if a.bedrooms:
            bedrooms.append(a.bedrooms)

    favorite_city = max(city_count, key=city_count.get) if city_count else None
    avg_price = sum(prices) / len(prices) if prices else 0
    preferred_bedrooms = max(set(bedrooms), key=bedrooms.count) if bedrooms else None

    properties = Property.query.filter_by(approved=True).all()

    def score(p):
        s = property_score(p)

        if favorite_city and p.location and favorite_city.lower() in p.location.lower():
            s += 50

        if avg_price and p.price and abs(p.price - avg_price) < avg_price * 0.3:
            s += 30

        if preferred_bedrooms and p.bedrooms == preferred_bedrooms:
            s += 20

        return s

    return sorted(properties, key=score, reverse=True)[:8]