from flask import Flask, render_template, request
import json

app = Flask(__name__)

# Load plant database at startup
with open("plant_database.json", "r", encoding="utf-8") as f:
    PLANT_DB = json.load(f)


def get_recommendations(region, soil, wants_fruit):
    """
    Simple rule-based recommendation using PLANT_DB.
    region: string key, e.g. 'Gujarat'
    soil: string key, e.g. 'clayey'
    wants_fruit: bool
    """
    try:
        data = PLANT_DB["regions"][region][soil]
    except KeyError:
        return {
            "plants": [],
            "cost_per_tree": 500,
            "maturity_months": 24,
        }

    plants = []

    if wants_fruit and "fruit_trees" in data:
        plants.extend(data["fruit_trees"])

    if "oxygen_trees" in data:
        for p in data["oxygen_trees"]:
            if p not in plants:
                plants.append(p)

    if not plants and "native_trees" in data:
        plants = data["native_trees"]

    return {
        "plants": plants,
        "cost_per_tree": data.get("cost_per_tree", 500),
        "maturity_months": data.get("maturity_months", 24),
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/assess", methods=["GET", "POST"])
def assess():
    if request.method == "POST":
        region = request.form.get("region")
        soil = request.form.get("soil")
        wants_fruit = request.form.get("wants_fruit") == "on"

        rec = get_recommendations(region, soil, wants_fruit)

        return render_template(
            "results.html",
            region=region,
            soil=soil,
            recommendations=rec,
        )

    regions = sorted(PLANT_DB["regions"].keys())
    soils = ["clayey", "sandy", "loamy"]
    return render_template("assess.html", regions=regions, soils=soils)


if __name__ == "__main__":
    app.run(debug=True)
