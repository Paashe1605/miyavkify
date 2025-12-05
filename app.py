from flask import Flask, render_template, request
import json

# Create Flask app
app = Flask(__name__)

# Load plant data once at startup
with open("plant_database.json", "r", encoding="utf-8") as f:
    PLANT_DB = json.load(f)


def get_recommendations(region, soil, wants_fruit):
    """
    Pick tree list + cost + maturity for a region/soil.
    """
    try:
        data = PLANT_DB["regions"][region][soil]
    except KeyError:
        # Fallback if combo not in JSON
        return {
            "plants": [],
            "cost_per_tree": 500,
            "maturity_months": 24,
        }

    plants = []

    # Add fruit trees first if user wants them
    if wants_fruit and "fruit_trees" in data:
        plants.extend(data["fruit_trees"])

    # Add oxygen trees, avoid duplicates
    if "oxygen_trees" in data:
        for p in data["oxygen_trees"]:
            if p not in plants:
                plants.append(p)

    # If still empty, use native trees
    if not plants and "native_trees" in data:
        plants = data["native_trees"]

    return {
        "plants": plants,
        "cost_per_tree": data.get("cost_per_tree", 500),
        "maturity_months": data.get("maturity_months", 24),
    }


def estimate_tree_count(area_sqm):
    """
    Estimate trees based on area (≈4 trees per m²).
    """
    try:
        area = float(area_sqm)
    except (TypeError, ValueError):
        return 0
    if area <= 0:
        return 0
    return int(area * 4)


def compute_impact(tree_count, cost_per_tree):
    """
    Rough CO₂, oxygen and cost impact.
    """
    if tree_count <= 0:
        return {
            "co2_kg_per_year": 0,
            "oxygen_kg_per_year": 0,
            "total_cost": 0,
        }

    # Very approximate constants (for demo)
    co2_per_tree = 20      # kg CO₂ / tree / year
    oxygen_per_tree = 22   # kg O₂ / tree / year

    co2_total = tree_count * co2_per_tree
    oxygen_total = tree_count * oxygen_per_tree
    total_cost = tree_count * cost_per_tree

    return {
        "co2_kg_per_year": co2_total,
        "oxygen_kg_per_year": oxygen_total,
        "total_cost": total_cost,
    }


@app.route("/")
def index():
    """
    Show landing page.
    """
    return render_template("index.html")


@app.route("/assess", methods=["GET", "POST"])
def assess():
    """
    Show form (GET) or results (POST).
    """
    if request.method == "POST":
        # Read form inputs
        region = request.form.get("region")
        soil = request.form.get("soil")
        wants_fruit = request.form.get("wants_fruit") == "on"
        area_sqm = request.form.get("area_sqm")

        # Core logic
        rec = get_recommendations(region, soil, wants_fruit)
        tree_count = estimate_tree_count(area_sqm)
        impact = compute_impact(tree_count, rec["cost_per_tree"])

        # Render results page with all data
        return render_template(
            "results.html",
            region=region,
            soil=soil,
            area_sqm=area_sqm,
            recommendations=rec,
            tree_count=tree_count,
            impact=impact,
        )

    # For GET: show blank form
    regions = sorted(PLANT_DB["regions"].keys())
    soils = ["clayey", "sandy", "loamy"]
    return render_template("assess.html", regions=regions, soils=soils)


if __name__ == "__main__":
    # Run dev server with auto-reload and debug
    app.run(debug=True)
