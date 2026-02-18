import datetime
from datetime import datetime
import os
print("FLASK ROOT:", os.getcwd())
from flask import Flask, render_template, request, redirect, session
import json, os, uuid

from flask import Flask
app = Flask(__name__, template_folder='templates', static_folder='static')


app.secret_key = "supersecretkey"


print("FLASK ROOT:", app.root_path)
print("TEMPLATES:", app.template_folder)
print("STATIC:", app.static_folder)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_FILE = "db.json"

def load_db():
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_average_rates(builders, zone):
    matched = [b for b in builders if b.get("zone") == zone]

    if not matched:
        return None

    avg = {}
    keys = [
        "basic_rate", "standard_rate", "premium_rate", "luxury_rate",
        "structure_rate", "labor_cost", "plot_rate"
    ]

    for key in keys:
        total = sum(float(b.get(key, 0)) for b in matched)
        avg[key] = total / len(matched)

    return avg

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = load_db()
        user = {
            "id": str(uuid.uuid4()),
            "username": request.form["username"],
            "password": request.form["password"]
        }
        data["users"].append(user)
        save_db(data)
        return redirect("/login")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = load_db()

        for user in data["users"]:
            if (
                user["username"] == request.form["username"]
                and user["password"] == request.form["password"]
            ):
                session["user"] = user["username"]
                role = user.get("role")

                if role == "admin":
                    return redirect("/admin_dashboard")
                elif role == "builder":
                    return redirect("/builder_dashboard")
                elif role == "client":
                    return redirect("/client_dashboard")
                else:
                    return redirect("/")

        return "Invalid Credentials"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")


@app.route("/")
def index():
    if "user" not in session:
        return redirect("/login")
    return render_template("index.html")


@app.route("/client_form/<role>")
def client_form(role):
    data = load_db()
    user = next(u for u in data["users"] if u["username"] == session["user"])
    if user.get("role") == "builder":
        return "You are registered as builder"
    if "user" not in session:
        return redirect("/login")
    return render_template("form_client.html", role=role)


@app.route("/builder_form")
def builder_form():
    data = load_db()
    user = next(u for u in data["users"] if u["username"] == session["user"])
    if user.get("role") == "client":
        return "You are registered as client"
    if "user" not in session:
        return redirect("/login")
    return render_template("form_builder.html")


@app.route("/submit_client", methods=["POST"])
def submit_client():
    data = load_db()

    aadhaar = request.files.get("aadhaar")

    aadhaar_path = ""
    if aadhaar and aadhaar.filename != "":
        aadhaar_path = os.path.join(UPLOAD_FOLDER, aadhaar.filename)
        aadhaar.save(aadhaar_path)

    client = dict(request.form)
    client["aadhaar"] = aadhaar_path
    client["id"] = str(uuid.uuid4())
    client["status"] = "pending"

    # -------- Estimation --------
    builders = data.get("builders", [])
    zone = client.get("zone")

    estimate = None

    if builders:
        rates = get_average_rates(builders, zone)

        if rates:
            plot = float(client.get("plot_size", 0))

            if client["role"] == "want_construction":
                floors = int(client.get("floors", 1))
                purpose = client.get("purpose")
                only_structure = client.get("only_structure")

                total_area = plot * floors

                if only_structure == "yes":
                    estimate = total_area * rates["structure_rate"]
                else:
                    if purpose == "basic":
                        rate = rates["basic_rate"]
                    elif purpose == "standard":
                        rate = rates["standard_rate"]
                    elif purpose == "premium":
                        rate = rates["premium_rate"]
                    else:
                        rate = rates["luxury_rate"]

                    estimate = total_area * rate + (total_area * rates["labor_cost"])

            elif client["role"] == "sell":
                estimate = plot * rates["plot_rate"]

            elif client["role"] == "rent_out":
                value = plot * rates["plot_rate"]
                estimate = value * 0.008

            elif client["role"] == "rent_in":
                estimate = "Contact owner for rent"

            elif client["role"] == "purchase":
                estimate = "Contact seller for price"

    if estimate is None:
        estimate = "Not available"

    client["estimate"] = estimate
    client["user"] = session["user"]

    # -------- Update user role --------
    for u in data["users"]:
        if u["username"] == session["user"]:
            u["role"] = "client"

    client["status"] = "pending"
    client["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # -------- Save client --------
    data["clients"].append(client)
    save_db(data)

    return redirect("/client_dashboard")


@app.route("/submit_builder", methods=["POST"])
def submit_builder():
    data = load_db()

    aadhaar = request.files.get("aadhaar")

    aadhaar_path = ""
    if aadhaar and aadhaar.filename != "":
        aadhaar_path = os.path.join(UPLOAD_FOLDER, aadhaar.filename)
        aadhaar.save(aadhaar_path)


    profile = request.files.get("profile")

    profile_path = ""
    if profile and profile.filename != "":
        profile_path = os.path.join(UPLOAD_FOLDER, profile.filename)
        profile.save(profile_path)


    builder = dict(request.form)
    builder["id"] = str(uuid.uuid4())
    builder["status"] = "pending"
    builder["aadhaar"] = aadhaar_path
    builder["profile"] = profile_path
    # mark user as builder
    data = load_db()
    for u in data["users"]:
        if u["username"] == session["user"]:
            u["role"] = "builder"
    save_db(data)
    builder["user"] = session["user"]

    builder["status"] = "pending"
    builder["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data["builders"].append(builder)
    save_db(data)
    return redirect("/builder_dashboard")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    data = load_db()
    return render_template("dashboard.html", data=data)


@app.route("/listings")
def listings():
    if "user" not in session:
        return redirect("/login")

    data = load_db()
    reviews = data.get("reviews", [])

    # function to calculate builder rating
    def get_rating(builder_user):
        r = [x for x in reviews if x["builder"] == builder_user]
        if not r:
            return 0
        return round(sum(x["rating"] for x in r) / len(r), 2)

    sell = [c for c in data["clients"] if c["role"] == "sell"]
    rent = [c for c in data["clients"] if c["role"] == "rent"]
    construction = [c for c in data["clients"] if c["role"] == "construction"]

    return render_template(
        "listings.html",
        sell=sell,
        rent=rent,
        construction=construction,
        builders=data["builders"],
        get_rating=get_rating
    )


@app.route("/client_dashboard")
def client_dashboard():
    if "user" not in session:
        return redirect("/login")

    data = load_db()

    # get only this user's APPROVED client entries
    clients = [
        c for c in data["clients"]
        if c.get("user") == session["user"]
        and c.get("status") == "approved"
    ]

    # get approved builders of same zone as first client
    matched_builders = []
    if clients:
        zone = clients[0].get("zone")
        matched_builders = [
            b for b in data["builders"]
            if b.get("zone") == zone
            and b.get("status") == "approved"
        ]

    return render_template(
        "client_dashboard.html",
        clients=clients,
        builders=matched_builders
    )


@app.route("/builder_dashboard")
def builder_dashboard():
    if "user" not in session:
        return redirect("/login")

    data = load_db()

    # Find approved builder of this user
    builder = next(
        (b for b in data["builders"]
         if b.get("user") == session["user"]
         and b.get("status") == "approved"),
        None
    )

    if not builder:
        return "Builder not approved yet or please register first"

    zone = builder.get("zone")

    # Only approved clients from same zone
    zone_clients = [
        c for c in data["clients"]
        if c.get("zone") == zone
        and c.get("status") == "approved"
    ]

    reviews = [
        r for r in data["reviews"]
        if r["builder"] == session["user"]
    ]

    avg = 0
    trust_score = 0

    if reviews:
        avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
        avg_quality = sum(r["quality"] for r in reviews) / len(reviews)
        avg_communication = sum(r["communication"] for r in reviews) / len(reviews)
        on_time_rate = sum(r["on_time"] for r in reviews) / len(reviews)

        trust_score = (
            (avg_rating * 0.4) +
            (avg_quality * 0.25) +
            (avg_communication * 0.2) +
            (on_time_rate * 5 * 0.15)
        )

        avg = round(avg_rating, 2)
        trust_score = round(trust_score, 2)

    return render_template(
        "builder_dashboard.html",
        clients=zone_clients,
        reviews=reviews,
        avg=avg,
        trust_score=trust_score
    )


@app.route("/rate_builder", methods=["POST"])
def rate_builder_page():
    builder_user = request.form["builder_user"]
    return render_template("rate_builder.html", builder=builder_user)


@app.route("/submit_review", methods=["POST"])
def submit_review():
    if "user" not in session:
        return redirect("/login")

    data = load_db()

    review = {
        "builder": request.form["builder"],
        "client": session["user"],
        "rating": int(request.form["rating"]),
        "review": request.form["review"],
        "on_time": int(request.form.get("on_time", 0)),
        "quality": int(request.form.get("quality", 0)),
        "communication": int(request.form.get("communication", 0)),
        "verified": True,
        "timestamp": str(datetime.date.today())
    }

    data["reviews"].append(review)
    save_db(data)

    return redirect("/client_dashboard")


@app.route("/admin_dashboard")
def admin_dashboard():
    if "user" not in session:
        return redirect("/login")

    data = load_db()

    # check if logged in user is admin
    user = next((u for u in data["users"] if u["username"] == session["user"]), None)

    if not user or user.get("role") != "admin":
        return "Access denied"

    pending_clients = [c for c in data["clients"] if c.get("status") == "pending"]
    pending_builders = [b for b in data["builders"] if b.get("status") == "pending"]

    return render_template(
        "admin_dashboard.html",
        clients=pending_clients,
        builders=pending_builders
    )


@app.route("/approve_client/<id>")
def approve_client(id):
    data = load_db()
    for c in data["clients"]:
        if c["id"] == id:
            c["status"] = "approved"
    save_db(data)
    return redirect("/admin_dashboard")


@app.route("/reject_client/<id>")
def reject_client(id):
    data = load_db()
    data["clients"] = [c for c in data["clients"] if c["id"] != id]
    save_db(data)
    return redirect("/admin_dashboard")


@app.route("/approve_builder/<id>")
def approve_builder(id):
    data = load_db()
    for b in data["builders"]:
        if b["id"] == id:
            b["status"] = "approved"
    save_db(data)
    return redirect("/admin_dashboard")


@app.route("/reject_builder/<id>")
def reject_builder(id):
    data = load_db()
    data["builders"] = [b for b in data["builders"] if b["id"] != id]
    save_db(data)
    return redirect("/admin_dashboard")


@app.route("/leaderboard")
def leaderboard():
    data = load_db()

    approved_builders = [
        b for b in data["builders"]
        if b.get("status") == "approved"
    ]

    builder_scores = []

    for b in approved_builders:
        reviews = [
            r for r in data["reviews"]
            if r["builder"] == b["user"]
        ]

        trust_score = 0

        if reviews:
            avg_rating = sum(r["rating"] for r in reviews) / len(reviews)
            avg_quality = sum(r.get("quality", 0) for r in reviews) / len(reviews)
            avg_communication = sum(r.get("communication", 0) for r in reviews) / len(reviews)
            on_time_rate = sum(r.get("on_time", 0) for r in reviews) / len(reviews)

            trust_score = (
                (avg_rating * 0.4) +
                (avg_quality * 0.25) +
                (avg_communication * 0.2) +
                (on_time_rate * 5 * 0.15)
            )

        builder_scores.append({
            "builder": b,
            "trust_score": round(trust_score, 2)
        })

    # sort highest first
    builder_scores.sort(key=lambda x: x["trust_score"], reverse=True)

    return render_template("leaderboard.html", builders=builder_scores)


if __name__ == "__main__":
    app.run(debug=True)
