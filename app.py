from flask import Flask, render_template, request
import json
import os                      # for file paths
from datetime import datetime  # for timestamped filenames
from werkzeug.utils import secure_filename  # safe filenames for uploads

# Create Flask app
app = Flask(__name__)

# Upload + log configuration
UPLOAD_FOLDER = os.path.join("static", "uploads")
LOG_PATH = os.path.join("data", "progress_log.json")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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


def estimate_traditional_tree_count(area_sqm):
    """
    Estimate trees in a traditional plantation (≈1.5 trees per m²).
    """
    try:
        area = float(area_sqm)
    except (TypeError, ValueError):
        return 0
    if area <= 0:
        return 0
    return int(area * 1.5)


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


# ---------- Day 3 helpers: uploads + log ----------

def allowed_file(filename):
    """
    Check if file has an allowed extension.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_progress_log():
    """
    Read the JSON progress log from disk.
    """
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_progress_log(entries):
    """
    Write the JSON progress log to disk.
    """
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def save_progress_entry(region, soil, area_sqm, note, file_storage):
    """
    Save uploaded image + a log entry. Returns saved filename or None.
    """
    if not (file_storage and allowed_file(file_storage.filename)):
        return None

    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Safe, timestamped filename
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    original = secure_filename(file_storage.filename)
    filename = f"{timestamp}_{original}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    # Save file
    file_storage.save(filepath)

    # Append log entry
    entries = load_progress_log()
    entries.append(
        {
            "region": region,
            "soil": soil,
            "area_sqm": area_sqm,
            "note": note,
            "filename": filename,
            "created_at": timestamp,
        }
    )
    save_progress_log(entries)

    return filename


# ---------- Routes ----------

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

        # Miyawaki recommendations and impact
        rec = get_recommendations(region, soil, wants_fruit)
        tree_count = estimate_tree_count(area_sqm)
        impact = compute_impact(tree_count, rec["cost_per_tree"])

        # Traditional plantation scenario (lower density, slightly cheaper per tree)
        traditional_tree_count = estimate_traditional_tree_count(area_sqm)
        traditional_cost_per_tree = int(rec["cost_per_tree"] * 0.85)  # ~15% cheaper
        traditional_impact = compute_impact(traditional_tree_count, traditional_cost_per_tree)

        # Assume traditional plantations take about 2× longer to become stable
        traditional_maturity_months = int(rec["maturity_months"] * 2)

        # Simple ratios for explanation (avoid divide-by-zero)
        trees_ratio = 0
        cost_ratio = 0
        speed_ratio = 0
        if traditional_tree_count > 0:
            trees_ratio = round(tree_count / traditional_tree_count, 1)
        if traditional_impact["total_cost"] > 0:
            cost_ratio = round(impact["total_cost"] / traditional_impact["total_cost"], 1)
        if traditional_maturity_months > 0:
            speed_ratio = round(traditional_maturity_months / rec["maturity_months"], 1)

        comparison = {
            "trees_ratio": trees_ratio,
            "cost_ratio": cost_ratio,
            "speed_ratio": speed_ratio,
        }

        # Render results page with all data
        return render_template(
            "results.html",
            region=region,
            soil=soil,
            area_sqm=area_sqm,
            recommendations=rec,
            tree_count=tree_count,
            impact=impact,
            traditional_tree_count=traditional_tree_count,
            traditional_cost_per_tree=traditional_cost_per_tree,
            traditional_impact=traditional_impact,
            traditional_maturity_months=traditional_maturity_months,
            comparison=comparison,
        )

    # For GET: show blank form
    regions = sorted(PLANT_DB["regions"].keys())
    soils = ["clayey", "sandy", "loamy"]
    return render_template("assess.html", regions=regions, soils=soils)


@app.route("/progress", methods=["GET", "POST"])
def progress():
    """
    Upload a progress photo + note for a plot.
    """
    if request.method == "POST":
        # Hidden context fields
        region = request.form.get("region")
        soil = request.form.get("soil")
        area_sqm = request.form.get("area_sqm")
        note = request.form.get("note", "").strip()

        file = request.files.get("photo")

        saved_filename = save_progress_entry(region, soil, area_sqm, note, file)

        # Simple success / error flag
        success = saved_filename is not None

        return render_template(
            "progress.html",
            region=region,
            soil=soil,
            area_sqm=area_sqm,
            success=success,
        )

    # GET: show form, prefilled from query string
    region = request.args.get("region", "")
    soil = request.args.get("soil", "")
    area_sqm = request.args.get("area_sqm", "")

    return render_template(
        "progress.html",
        region=region,
        soil=soil,
        area_sqm=area_sqm,
        success=None,
    )


if __name__ == "__main__":
    # Run dev server with auto-reload and debug
    app.run(debug=True)
