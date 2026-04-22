from models import Property, UserActivity


# 🧠 BASE SCORING ENGINE
def property_score(p):

    score = 0

    # ⭐ featured boost
    if p.featured:
        score += 40

    # 🔥 boosted listing
    if p.featured_until:
        score += 25

    # 📍 city boost
    popular_cities = ["lagos", "abuja", "ilorin", "ibadan"]

    if p.location:
        for city in popular_cities:
            if city in p.location.lower():
                score += 20
                break

    # 💰 price sweet spot
    if p.price and 500000 <= p.price <= 5000000:
        score += 15

    # 🏠 bedroom preference
    if hasattr(p, "bedrooms") and p.bedrooms in [1, 2, 3]:
        score += 10

    return score


# 🧠 AI RECOMMENDATION SYSTEM
def get_recommendations(user_id):

    activities = UserActivity.query.filter_by(user_id=user_id).all()

    properties = Property.query.filter(Property.approved == True).all()

    # 🟡 NEW USER FALLBACK
    if not activities:
        return sorted(properties, key=property_score, reverse=True)[:10]

    city_count = {}
    prices = []
    bedrooms = []

    for a in activities:

        if a.city:
            city_count[a.city] = city_count.get(a.city, 0) + 1

        if a.price:
            prices.append(a.price)

        if a.bedrooms:
            bedrooms.append(a.bedrooms)

    # 🟢 SAFE VALUES
    favorite_city = max(city_count, key=city_count.get) if city_count else None
    avg_price = sum(prices) / len(prices) if prices else None
    preferred_bedrooms = max(set(bedrooms), key=bedrooms.count) if bedrooms else None

    # 🧠 SCORING FUNCTION
    def score(p):

        s = property_score(p)

        # city preference
        if favorite_city and p.location:
            if favorite_city.lower() in p.location.lower():
                s += 50

        # price similarity
        if avg_price and p.price:
            if abs(p.price - avg_price) < avg_price * 0.3:
                s += 30

        # bedroom preference
        if preferred_bedrooms and hasattr(p, "bedrooms"):
            if p.bedrooms == preferred_bedrooms:
                s += 20

        return s

    return sorted(properties, key=score, reverse=True)[:10]