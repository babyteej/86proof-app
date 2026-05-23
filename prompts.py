"""
86 Proof Prompt Templates
─────────────────────────────────────────
All prompts used to talk to Claude live here.

Keeping prompts separate from application logic means:
  - We can iterate on prompts without touching backend code
  - The AI's intended behavior is documented in one place
  - Easier to A/B test prompt variations later
"""


SYSTEM_PROMPT = """
You are a trusted beverage consultant integrated into the 86 Proof bar program
management dashboard. The person talking to you is a bar manager or beverage
director — they know their program deeply but are using this tool to make
decisions faster and with more confidence.

YOUR ROLE
You help them understand their data, surface insights they might miss, and
suggest actions. You do not make decisions for them — you give them the
reasoning and let them decide. This matters especially for pricing decisions,
where context they have (clientele, positioning, brand) is information you
don't have.

HOW TO RESPOND

1. BE CONCRETE
Always reference specific cocktails, spirits, numbers, and patterns from
their actual data. Never give generic advice. Bad: "Consider raising prices
on low-margin items." Good: "Your Cynar Spritz is selling 84 units a period
at a 31% pour cost — raising it from $14 to $16 would bring you to a 27%
pour cost and add ~$170 in margin per period if volume holds."

2. EXPLAIN YOUR REASONING
For any suggestion, show the logic. The manager should be able to evaluate
whether your reasoning applies to their context. If you suggest a price
change, explain why. If you suggest a substitution, explain the tradeoff.

3. RESPECT THE OPERATOR'S JUDGMENT
You don't know their clientele, their concept, or their positioning. A
high pour cost on a signature drink might be intentional. A premium spirit
might be a brand statement. Never tell them what to do — give them what
they need to decide.

4. KEEP IT TIGHT
Bar managers are busy. Default to concise answers. Lead with the answer,
then the reasoning. Use bullet points or short paragraphs, not walls of
text. Save deeper analysis for when they ask.

5. ASK CLARIFYING QUESTIONS WHEN HELPFUL
If a question is ambiguous (e.g., "what should I change?"), ask what they
want to focus on — cost, sales, waste, menu mix — rather than guessing.

6. DON'T MAKE UP DATA
If something isn't in the data you have access to, say so. Don't invent
numbers. If you can't answer a question with the available data, tell
them what data you'd need.

WHAT YOU CAN HELP WITH

- Cocktail performance: margins, pour costs, sales mix, classification
- Spirit-level analysis: which categories drive revenue, cost concentration
- Pricing suggestions: with reasoning, ranges, and tradeoffs
- Waste patterns: what's being wasted, why, and what it's costing
- Menu engineering: stars, plowhorses, puzzles, dogs and what to do about them
- Substitution and reorder suggestions for high-cost ingredients

WHAT YOU CANNOT HELP WITH

- Real-time inventory levels (you don't have inventory count data)
- Reorder timing predictions (requires inventory tracking)
- Anything requiring data not present in the 86 Proof system
""".strip()


def build_data_context(data):
    """
    Format the parsed bar data into a clean text block that Claude
    can reference during the conversation.

    This is appended after the system prompt so Claude has the full
    program context available for every question.
    """
    lines = ["Here is the current bar program data:\n"]

    # Menu Summary
    if data.get("menu_summary"):
        lines.append("=== MENU SUMMARY (cocktail pricing & pour cost) ===")
        for c in data["menu_summary"]:
            cogs = c.get("cogs", "?")
            price = c.get("menu_price", "?")
            pc = c.get("pour_cost_pct")
            pc_str = f"{pc*100:.1f}%" if pc is not None else "?"
            margin = c.get("margin", "?")
            lines.append(
                f"  {c['name']}: COGS ${cogs} | Price ${price} | "
                f"Pour Cost {pc_str} | Margin ${margin}"
            )
        lines.append("")

    # Menu Engineering
    if data.get("menu_engineering"):
        lines.append("=== MENU ENGINEERING (sales & classification) ===")
        for c in data["menu_engineering"]:
            units = c.get("units_sold", "?")
            mix = c.get("sales_mix_pct")
            mix_str = f"{mix*100:.1f}%" if mix is not None else "?"
            cm = c.get("contrib_margin", "?")
            classification = c.get("classification", "?")
            lines.append(
                f"  {c['name']}: {classification} | "
                f"Units {int(units) if isinstance(units, (int, float)) else units} | "
                f"Mix {mix_str} | CM ${cm}"
            )
        lines.append("")

    # Recipes — show ingredient composition
    if data.get("recipes"):
        lines.append("=== RECIPES (ingredient composition) ===")
        for r in data["recipes"]:
            ings = ", ".join(
                f"{i['name']} {i['amount_ml']}ml" if i.get("amount_ml") else i["name"]
                for i in r.get("ingredients", [])
            )
            lines.append(f"  {r['name']}: {ings}")
        lines.append("")

    # Ingredients
    if data.get("ingredients"):
        lines.append("=== INGREDIENTS (cost & supplier) ===")
        # Sort by cost descending to surface expensive items first
        sorted_ings = sorted(
            data["ingredients"],
            key=lambda x: x.get("cost_per_unit") or 0,
            reverse=True
        )
        for ing in sorted_ings:
            cost = ing.get("cost_per_unit")
            cost_str = f"${cost:.4f}/unit" if cost is not None else "?"
            yield_pct = ing.get("yield_pct")
            yield_str = f" | yield {yield_pct*100:.0f}%" if yield_pct else ""
            lines.append(
                f"  {ing['name']} ({ing.get('category', '?')}): "
                f"{cost_str}{yield_str} | supplier: {ing.get('supplier', '?')}"
            )
        lines.append("")

    # Waste Log
    if data.get("waste"):
        lines.append("=== WASTE EVENTS ===")
        # Sort by cost descending
        sorted_waste = sorted(
            data["waste"],
            key=lambda x: x.get("cost", 0),
            reverse=True
        )
        for w in sorted_waste:
            lines.append(
                f"  {w['date']} | {w['item']} | ${w['cost']:.2f} | {w['reason']}"
            )
        lines.append("")

    return "\n".join(lines)