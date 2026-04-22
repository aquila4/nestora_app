from flask import Blueprint, jsonify, request
from models import Property
from services.recommendation import get_recommendations

api = Blueprint("api", __name__)


# 🏠 ALL PROPERTIES
@api.route("/properties")
def get_properties():

    limit = request.args.get("limit", 50)

    properties = Property.query.filter(Property.approved == True)\
        .order_by(Property.created_at.desc())\
        .limit(int(limit))\
        .all()

    return jsonify({
        "status": "success",
        "count": len(properties),
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "location": p.location,
                "price": p.price,
                "featured": p.featured,
                "image": f"/static/uploads/{p.image}" if p.image else "/static/uploads/default.jpg"
            }
            for p in properties
        ]
    })


# 🔍 SEARCH
@api.route("/search")
def search_properties():

    q = request.args.get("q", "")

    properties = Property.query.filter(
        (Property.title.ilike(f"%{q}%")) |
        (Property.location.ilike(f"%{q}%"))
    ).all()

    return jsonify({
        "status": "success",
        "count": len(properties),
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "location": p.location,
                "price": p.price,
                "image": f"/static/uploads/{p.image}" if p.image else "/static/uploads/default.jpg"
            }
            for p in properties
        ]
    })


# 🧠 RECOMMENDATIONS (USES YOUR AI ENGINE)
@api.route("/recommendations/<int:user_id>")
def recommendations(user_id):

    recs = get_recommendations(user_id)

    return jsonify({
        "status": "success",
        "count": len(recs),
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "location": p.location,
                "price": p.price,
                "image": f"/static/uploads/{p.image}" if p.image else "/static/uploads/default.jpg"
            }
            for p in recs
        ]
    })


# 🏡 SINGLE PROPERTY
@api.route("/property/<int:id>")
def get_property(id):

    p = Property.query.get_or_404(id)

    return jsonify({
        "status": "success",
        "data": {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "location": p.location,
            "price": p.price,
            "bedrooms": p.bedrooms,
            "featured": p.featured,
            "image": f"/static/uploads/{p.image}" if p.image else "/static/uploads/default.jpg"
        }
    })