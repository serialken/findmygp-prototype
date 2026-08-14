"""Pricing logic — server-side port of the prototype's computePrice(), now
fed by real distances instead of a pseudo-random hash. This MUST be computed
server-side (never trust a price sent by the client) since it is what gets
charged via Stripe.
"""

FRAGILE_SURCHARGE = 8.0


def compute_price(base_price: float, price_per_km: float, distance_km: float, fragile: bool) -> dict:
    distance_price = round(price_per_km * distance_km, 2)
    fragile_surcharge = FRAGILE_SURCHARGE if fragile else 0.0
    total = round(base_price + distance_price + fragile_surcharge, 2)
    return {
        "base_price": base_price,
        "distance_price": distance_price,
        "fragile_surcharge": fragile_surcharge,
        "total_price": total,
    }
