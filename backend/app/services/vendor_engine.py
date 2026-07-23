def rank_vendors(vendors):
    if not vendors:
        return []

    max_price = max(v.price for v in vendors)
    min_price = min(v.price for v in vendors)

    ranked = []

    for v in vendors:
        price_score = 1 - ((v.price - min_price) / (max_price - min_price + 1e-6))
        score = (0.5 * v.rating / 5) + (0.5 * price_score)
        ranked.append((score, v))

    ranked.sort(reverse=True, key=lambda x: x[0])
    return [v for _, v in ranked]