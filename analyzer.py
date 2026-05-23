"""
86 Proof Dashboard Analyzer
─────────────────────────────────────────
Computes dashboard metrics from parsed bar program data.

All metrics here are deterministic calculations — no AI.
The AI layer kicks in for chat and the deeper analysis pages.
"""

# Default targets — can be overridden per venue later
DEFAULT_POUR_COST_TARGET = 0.20
DEFAULT_POUR_COST_WARNING = 0.25
DEFAULT_WASTE_TARGET_PCT = 0.02  # 2% of beverage sales is a reasonable target


def get_pour_cost_health(menu_summary, target=DEFAULT_POUR_COST_TARGET):
    """
    Calculate average pour cost across all cocktails on the menu.
    Returns the average and comparison to target.
    """
    pour_costs = [c["pour_cost_pct"] for c in menu_summary
                  if c.get("pour_cost_pct") is not None]

    if not pour_costs:
        return {"value": None, "target": target, "status": "no_data"}

    average = sum(pour_costs) / len(pour_costs)

    if average <= target:
        status = "on_target"
    elif average <= target * 1.10:  # within 10% of target
        status = "slightly_over"
    else:
        status = "over"

    return {
        "value": round(average, 4),
        "target": target,
        "status": status,
        "delta": round(average - target, 4),
    }


def get_cocktails_above_warning(menu_summary, warning=DEFAULT_POUR_COST_WARNING):
    """Count cocktails with pour cost above the warning threshold."""
    flagged = [c for c in menu_summary
               if c.get("pour_cost_pct") is not None
               and c["pour_cost_pct"] > warning]

    return {
        "count": len(flagged),
        "total": len(menu_summary),
        "warning_threshold": warning,
        "flagged_cocktails": [c["name"] for c in flagged],
    }


def get_top_cocktail(menu_engineering):
    """
    Identify the top performing cocktail by contribution margin × units sold.
    This is total dollar contribution, not just margin per unit.
    """
    scored = []
    for c in menu_engineering:
        cm = c.get("contrib_margin")
        units = c.get("units_sold")
        if cm is not None and units is not None:
            scored.append({
                "name": c["name"],
                "total_contribution": cm * units,
                "units_sold": units,
                "contrib_margin": cm,
                "classification": c.get("classification", ""),
            })

    if not scored:
        return None

    top = max(scored, key=lambda x: x["total_contribution"])
    return top


def get_total_revenue(menu_engineering):
    """Sum menu_price × units_sold across all cocktails."""
    total = 0
    for c in menu_engineering:
        price = c.get("menu_price")
        units = c.get("units_sold")
        if price is not None and units is not None:
            total += price * units
    return round(total, 2)


def get_total_waste(waste_log):
    """Sum the cost of all waste events."""
    total = sum(w["cost"] for w in waste_log if w.get("cost"))
    return round(total, 2)


def get_waste_health(waste_log, total_revenue, target_pct=DEFAULT_WASTE_TARGET_PCT):
    """
    Compare waste cost to revenue. Industry rule of thumb: waste should be
    under 2% of beverage sales.
    """
    waste_total = get_total_waste(waste_log)

    if total_revenue == 0:
        return {"value": waste_total, "target_pct": target_pct, "status": "no_data"}

    waste_pct = waste_total / total_revenue

    if waste_pct <= target_pct:
        status = "on_target"
    elif waste_pct <= target_pct * 1.5:
        status = "slightly_over"
    else:
        status = "over"

    return {
        "waste_dollars": waste_total,
        "waste_pct": round(waste_pct, 4),
        "target_pct": target_pct,
        "status": status,
        "revenue": total_revenue,
    }


def get_top_spirit_category(menu_engineering, recipes, ingredients):
    """
    Cross-reference recipes against sales to find the spirit category
    driving the most revenue.

    Logic:
      1. Build a lookup: ingredient name → category
      2. For each cocktail sold, look at its recipe ingredients
      3. Attribute the cocktail's revenue equally across its spirit categories
      4. Aggregate across all cocktails
    """
    # Build ingredient → category lookup
    ing_to_category = {}
    for ing in ingredients:
        name = ing.get("name", "").strip()
        category = ing.get("category", "").strip()
        if name and category:
            ing_to_category[name] = category

    # Build cocktail → recipe lookup
    cocktail_to_recipe = {}
    for r in recipes:
        cocktail_to_recipe[r["name"]] = r.get("ingredients", [])

    # Aggregate revenue by category
    category_revenue = {}

    for c in menu_engineering:
        name = c["name"]
        price = c.get("menu_price")
        units = c.get("units_sold")
        if not (price and units):
            continue

        cocktail_revenue = price * units
        recipe_ingredients = cocktail_to_recipe.get(name, [])

        # Find spirit categories in this recipe
        # (we filter out non-spirit categories like Citrus, Bitters, etc)
        non_spirit_categories = {"Citrus", "Bitters", "Syrup", "Garnish",
                                  "Mixer", "Soda", "Juice", "Fruit"}

        spirit_categories_in_recipe = set()
        for ing in recipe_ingredients:
            cat = ing_to_category.get(ing["name"], "")
            if cat and cat not in non_spirit_categories:
                spirit_categories_in_recipe.add(cat)

        if not spirit_categories_in_recipe:
            continue

        # Distribute revenue equally across spirit categories
        share = cocktail_revenue / len(spirit_categories_in_recipe)
        for cat in spirit_categories_in_recipe:
            category_revenue[cat] = category_revenue.get(cat, 0) + share

    if not category_revenue:
        return None

    top_category = max(category_revenue.items(), key=lambda x: x[1])
    return {
        "category": top_category[0],
        "revenue": round(top_category[1], 2),
        "all_categories": {k: round(v, 2) for k, v in
                           sorted(category_revenue.items(),
                                  key=lambda x: x[1],
                                  reverse=True)},
    }


def build_dashboard_metrics(data):
    """
    Main entry point. Takes the full parsed data dict and returns
    all 6 dashboard metrics in one object.
    """
    menu_summary = data.get("menu_summary", [])
    menu_engineering = data.get("menu_engineering", [])
    recipes = data.get("recipes", [])
    ingredients = data.get("ingredients", [])
    waste_log = data.get("waste", [])

    total_revenue = get_total_revenue(menu_engineering)

    return {
        "pour_cost": get_pour_cost_health(menu_summary),
        "waste": get_waste_health(waste_log, total_revenue),
        "above_warning": get_cocktails_above_warning(menu_summary),
        "top_cocktail": get_top_cocktail(menu_engineering),
        "top_spirit_category": get_top_spirit_category(
            menu_engineering, recipes, ingredients
        ),
        "total_revenue": total_revenue,
    }