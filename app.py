from flask import Flask, render_template, request, session, redirect, url_for
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# ----------------- App + paths -----------------

app = Flask(__name__)

# Secret key for session cookies (OK to hardcode for hackathon demo)
app.secret_key = "miyavkify-demo-secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Upload + log configuration
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
LOG_PATH = os.path.join(BASE_DIR, "data", "progress_log.json")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Make sure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------- Plant data -----------------

with open(os.path.join(BASE_DIR, "plant_database.json"), "r", encoding="utf-8") as f:
    PLANT_DB = json.load(f)

# ----------------- Recommendation + impact -----------------


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

# ----------------- Day 3 helpers: uploads + log -----------------


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
    Uses secure_filename + save() as in the Flask upload pattern.
    """
    if not (file_storage and allowed_file(file_storage.filename)):
        return None

    # Safe, timestamped filename
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    original = secure_filename(file_storage.filename)
    filename = f"{timestamp}_{original}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # Save file
    file_storage.save(filepath)  # same pattern as recommended in Flask docs [web:0]

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
        "username": session.get("username"),
    }
)

    save_progress_log(entries)

    return filename
def load_progress_entries():
    """Read all saved progress entries from the JSON log."""
    if not os.path.exists(LOG_PATH):
        return []

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            entries = json.load(f)
            # Ensure it's a list
            if isinstance(entries, list):
                return entries
            return []
    except (json.JSONDecodeError, FileNotFoundError):
        return []
def compute_badges_for_user(user_entries):
    """
    Return a small list of badge labels based on number of entries
    for this user.
    """
    count = len(user_entries)
    badges = []

    if count >= 1:
        badges.append("Forest starter")          # uploaded first photo
    if count >= 3:
        badges.append("Consistent carer")        # came back multiple times
    if count >= 5:
        badges.append("Storyteller")             # rich photo history

    return badges


# ----------------- Routes -----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    """Very simple login: ask for a name and store it in session."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        if not username:
            # Just re-render with a tiny message; no flash needed
            return render_template("login.html", error="Please enter a name to continue.")
        session["username"] = username
        return redirect(url_for("index"))

    # If already logged in, send to home
    if "username" in session:
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Clear the session so user can switch identity."""
    session.pop("username", None)
    return redirect(url_for("login"))

def require_login():
    """Redirect to /login if no username set in session."""
    if "username" not in session:
        return redirect(url_for("login"))
    return None


@app.route("/")
def index():
    """
    Show landing page.
    """
    return render_template("index.html")


@app.route("/assess", methods=["GET", "POST"])
def assess():
    guard=require_login()
    if guard:
         return guard
    """
    Show form (GET) or results (POST).
    """
    if request.method == "POST":
        # Read form inputs
        region = request.form.get("region")
        soil = request.form.get("soil")
        wants_fruit = request.form.get("wants_fruit") == "on"
        area_sqm = request.form.get("area_sqm")

        # NEW: check if an image was uploaded
        image_file = request.files.get("plot_image")
        has_image = bool(image_file and image_file.filename)

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
            has_image=has_image,  # NEW: pass flag to template
        )

    # For GET: show blank form
    regions = sorted(PLANT_DB["regions"].keys())
    soils = ["clayey", "sandy", "loamy"]
    return render_template("assess.html", regions=regions, soils=soils)


@app.route("/progress", methods=["GET", "POST"])
def progress():
    guard=require_login()
    if guard:
         return guard
    """
    Upload a progress photo + note for a plot.
    Day 3 feature: uses save_progress_entry to store file + log.
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
@app.route("/gallery")
def gallery():
    guard = require_login()
    if guard:
        return guard

    entries = load_progress_entries()
    current_user = session.get("username")

    # Filter entries for this user only
    user_entries = [
        e for e in entries
        if e.get("username") == current_user
    ]

    # Newest first
    entries_sorted = sorted(
        user_entries,
        key=lambda e: e.get("created_at", ""),
        reverse=True,
    )

    # Compute simple badges for this user
    badges = compute_badges_for_user(user_entries)

    return render_template(
        "gallery.html",
        entries=entries_sorted,
        badges=badges,
    )



if __name__ == "__main__":
    # Run dev server with auto-reload and debug
    app.run(debug=True)
