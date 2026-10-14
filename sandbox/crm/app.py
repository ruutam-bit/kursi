"""Lietotne «CRM»: Flask, servera pusē renderēts HTML (viens process). Lietojuma loģika un maršruti.

Prasības: PRASIBAS.md. Visi dati ir sintētiski. Nav paredzēts produkcijai (N3: bez parolēm, mācību režīms).
Palaišana (no mapes sandbox/crm):  flask --app app run --debug
"""

import os
import re
import secrets
import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

import ai
import db
from db import CONTACT_BASES, INTERACTION_TYPES, NEXT_STATUS, ORG_TYPES, REQUEST_STATUSES, ROLES

app = Flask(__name__)
app.secret_key = os.environ.get("CRM_SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

STAFF = ("darbinieks", "vaditajs")
REG_NR_RE = re.compile(r"^\d{11}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d ]{8,15}$")
CONTACT_FIELDS = ("name", "position", "email", "phone", "basis", "basis_date")


@app.before_request
def setup():
    if not app.config.get("_db_ready"):
        db.init_db()
        app.config["_db_ready"] = True
    g.db = db.connect()
    g.today = date.today().isoformat()
    g.user = None
    if "user_id" in session:
        g.user = g.db.execute("SELECT * FROM lietotaji WHERE id = ?", (session["user_id"],)).fetchone()
    if request.method == "POST" and request.form.get("csrf") != session.get("csrf"):
        abort(400)


@app.teardown_request
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.context_processor
def template_globals():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(16)
    return {
        "csrf": session["csrf"], "ORG_TYPES": ORG_TYPES, "INTERACTION_TYPES": INTERACTION_TYPES,
        "REQUEST_STATUSES": REQUEST_STATUSES, "CONTACT_BASES": CONTACT_BASES, "ROLES": ROLES,
    }


def require(*roles):
    """N3: loma tiek pārbaudīta serverī katrā maršrutā."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("start"))
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def is_manager() -> bool:
    return g.user["role"] == "vaditajs"


def org_scope(alias: str = "o") -> tuple[str, tuple]:
    """Darbinieks redz tikai savas organizācijas, vadītājs — visas."""
    if is_manager():
        return "1 = 1", ()
    return f"{alias}.owner_id = ?", (g.user["id"],)


def get_org(org_id: int) -> sqlite3.Row:
    where, params = org_scope()
    org = g.db.execute(
        f"SELECT o.*, u.name AS owner_name FROM organizacijas o JOIN lietotaji u ON u.id = o.owner_id "
        f"WHERE o.id = ? AND {where}", (org_id, *params),
    ).fetchone()
    if org is None:
        abort(404)
    return org


def get_contact(contact_id: int) -> sqlite3.Row:
    contact = g.db.execute("SELECT * FROM kontakti WHERE id = ?", (contact_id,)).fetchone()
    if contact is None:
        abort(404)
    get_org(contact["org_id"])
    return contact


def log_access(entity: str, entity_id: int, action: str) -> None:
    """N2 piekļuves žurnāls: kas, ko, kad skatīja vai mainīja."""
    with g.db:
        g.db.execute(
            "INSERT INTO piekluves_zurnals (user_id, entity, entity_id, action) VALUES (?, ?, ?, ?)",
            (g.user["id"], entity, entity_id, action),
        )


def log_ai(component: str, org_id: int, model: str, outcome: str, interaction_id: int | None = None) -> None:
    with g.db:
        g.db.execute(
            "INSERT INTO mi_zurnals (user_id, component, org_id, model, outcome, interaction_id) VALUES (?, ?, ?, ?, ?, ?)",
            (g.user["id"], component, org_id, model, outcome, interaction_id),
        )


def overdue_sql(alias: str = "r") -> str:
    """Kavēts ir aprēķins (termiņš pagājis un nav atbildēts), nevis krāsa."""
    return f"({alias}.status != 'atbildets' AND {alias}.due_date < date('now', 'localtime'))"


def form_value(name: str) -> str:
    return request.form.get(name, "").strip()


def safe_next(default: str) -> str:
    target = request.form.get("next", "")
    return target if target.startswith("/") and not target.startswith("//") else default


def valid_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


# --- Visi: sākums / loma, F9 kopsavilkums, F8 paziņojums ---------------------

@app.get("/sakums")
def start():
    users = g.db.execute("SELECT * FROM lietotaji ORDER BY id").fetchall()
    return render_template("start.html", users=users)


@app.post("/sakums")
def choose_user():
    user = g.db.execute("SELECT id FROM lietotaji WHERE id = ?", (request.form.get("user_id", type=int),)).fetchone()
    if user is None:
        users = g.db.execute("SELECT * FROM lietotaji ORDER BY id").fetchall()
        return render_template("start.html", users=users, error="Izvēlies lietotāju."), 400
    csrf = session.get("csrf")
    session.clear()
    session["user_id"] = user["id"]
    session["csrf"] = csrf
    return redirect(url_for("dashboard"))


@app.post("/iziet")
def logout():
    session.clear()
    return redirect(url_for("start"))


@app.get("/")
@require(*STAFF, "administrators")
def dashboard():
    if g.user["role"] == "administrators":
        return redirect(url_for("admin"))
    where, params = org_scope()
    stats = {
        "orgs": g.db.execute(f"SELECT COUNT(*) FROM organizacijas o WHERE {where}", params).fetchone()[0],
        "open": g.db.execute(
            f"SELECT COUNT(*) FROM pieprasijumi r JOIN organizacijas o ON o.id = r.org_id "
            f"WHERE r.status != 'atbildets' AND {where}", params).fetchone()[0],
        "overdue": g.db.execute(
            f"SELECT COUNT(*) FROM pieprasijumi r JOIN organizacijas o ON o.id = r.org_id "
            f"WHERE {overdue_sql()} AND {where}", params).fetchone()[0],
    }
    tasks = todays_tasks()
    stats["tasks"] = len(tasks)
    recent = g.db.execute(
        f"SELECT i.*, o.name AS org_name FROM mijiedarbibas i JOIN organizacijas o ON o.id = i.org_id "
        f"WHERE {where} ORDER BY i.date DESC, i.id DESC LIMIT 5", params,
    ).fetchall()
    return render_template("dashboard.html", stats=stats, today_tasks=tasks, recent=recent)


@app.get("/pieklustamiba")
def accessibility():
    return render_template("accessibility.html")


def todays_tasks() -> list[sqlite3.Row]:
    return g.db.execute(
        "SELECT t.*, o.name AS org_name, r.title AS request_title FROM uzdevumi t "
        "LEFT JOIN organizacijas o ON o.id = t.org_id LEFT JOIN pieprasijumi r ON r.id = t.request_id "
        "WHERE t.user_id = ? AND t.done = 0 AND t.due_date <= date('now', 'localtime') ORDER BY t.due_date",
        (g.user["id"],),
    ).fetchall()


# --- Organizācijas: F1 saraksts + F6 meklēšana, F1 kartīte, F2 kontakta forma --

@app.get("/organizacijas")
@require(*STAFF)
def orgs():
    where, params = org_scope()
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    sql = (f"SELECT o.*, u.name AS owner_name, "
           f"(SELECT MAX(date) FROM mijiedarbibas i WHERE i.org_id = o.id) AS last_contact "
           f"FROM organizacijas o JOIN lietotaji u ON u.id = o.owner_id WHERE {where}")
    org_params = params
    if q:
        sql += " AND (o.name LIKE ? OR o.reg_nr LIKE ?)"
        org_params = (*params, like, like)
    rows = g.db.execute(sql + " ORDER BY o.name", org_params).fetchall()
    contacts = requests_ = None
    if q:  # F6: viens lauks pāri organizācijām, kontaktiem un pieprasījumiem
        contacts = g.db.execute(
            f"SELECT c.id, c.name, c.position, c.org_id, o.name AS org_name FROM kontakti c "
            f"JOIN organizacijas o ON o.id = c.org_id "
            f"WHERE (c.name LIKE ? OR c.position LIKE ? OR c.email LIKE ?) AND {where} ORDER BY c.name",
            (like, like, like, *params)).fetchall()
        requests_ = g.db.execute(
            f"SELECT r.*, o.name AS org_name, {overdue_sql()} AS overdue FROM pieprasijumi r "
            f"JOIN organizacijas o ON o.id = r.org_id WHERE r.title LIKE ? AND {where} ORDER BY r.due_date",
            (like, *params)).fetchall()
    return render_template("orgs.html", orgs=rows, q=q, contacts=contacts, found_requests=requests_)


def org_form_errors(data: dict, org_id: int | None) -> dict:
    errors = {}
    if not data["name"]:
        errors["name"] = "Ievadi organizācijas nosaukumu."
    if not REG_NR_RE.match(data["reg_nr"]):
        errors["reg_nr"] = "Reģistrācijas numuram jābūt 11 cipariem, piemēram, 40003000001."
    elif g.db.execute("SELECT 1 FROM organizacijas WHERE reg_nr = ? AND id IS NOT ?",
                      (data["reg_nr"], org_id)).fetchone():
        errors["reg_nr"] = "Organizācija ar šādu reģistrācijas numuru jau ir sistēmā."
    if data["type"] not in ORG_TYPES:
        errors["type"] = "Izvēlies organizācijas veidu."
    if not g.db.execute("SELECT 1 FROM lietotaji WHERE id = ? AND role IN ('darbinieks', 'vaditajs')",
                        (data["owner_id"],)).fetchone():
        errors["owner_id"] = "Izvēlies atbildīgo darbinieku."
    return errors


def read_org_form() -> dict:
    owner = request.form.get("owner_id", type=int)
    return {
        "name": form_value("name"), "reg_nr": form_value("reg_nr"), "type": form_value("type"),
        # Darbinieks var izveidot organizāciju tikai sev (N3)
        "owner_id": owner if is_manager() else g.user["id"],
    }


def render_org_form(org, data, errors, status=200):
    users = g.db.execute("SELECT * FROM lietotaji WHERE role IN ('darbinieks', 'vaditajs') ORDER BY name").fetchall()
    return render_template("org_form.html", org=org, data=data, errors=errors, users=users), status


@app.route("/organizacijas/jauna", methods=["GET", "POST"])
@require(*STAFF)
def org_new():
    if request.method == "GET":
        return render_org_form(None, {"owner_id": g.user["id"]}, {})
    data = read_org_form()
    errors = org_form_errors(data, None)
    if errors:
        return render_org_form(None, data, errors, 422)
    with g.db:
        cur = g.db.execute("INSERT INTO organizacijas (name, reg_nr, type, owner_id) VALUES (?, ?, ?, ?)",
                           (data["name"], data["reg_nr"], data["type"], data["owner_id"]))
    log_access("organizacija", cur.lastrowid, "izveidota")
    flash("Organizācija izveidota.")
    return redirect(url_for("org_detail", org_id=cur.lastrowid))


@app.route("/organizacijas/<int:org_id>/labot", methods=["GET", "POST"])
@require(*STAFF)
def org_edit(org_id):
    org = get_org(org_id)
    if request.method == "GET":
        return render_org_form(org, dict(org), {})
    data = read_org_form()
    if not is_manager():
        data["owner_id"] = org["owner_id"]
    errors = org_form_errors(data, org_id)
    if errors:
        return render_org_form(org, data, errors, 422)
    with g.db:
        g.db.execute("UPDATE organizacijas SET name = ?, reg_nr = ?, type = ?, owner_id = ? WHERE id = ?",
                     (data["name"], data["reg_nr"], data["type"], data["owner_id"], org_id))
    log_access("organizacija", org_id, "mainīta")
    flash("Izmaiņas saglabātas.")
    return redirect(url_for("org_detail", org_id=org_id))


@app.get("/organizacijas/<int:org_id>")
@require(*STAFF)
def org_detail(org_id):
    org = get_org(org_id)
    contacts = g.db.execute("SELECT * FROM kontakti WHERE org_id = ? ORDER BY name", (org_id,)).fetchall()
    # Kartītē redzami kontaktpersonu dati, tāpēc katra atvēršana tiek žurnalēta (N2).
    log_access("organizacija", org_id, f"skatīta kartīte ({len(contacts)} kontakti)")
    interactions = g.db.execute(
        "SELECT i.*, u.name AS user_name, "
        "(SELECT GROUP_CONCAT(c.name, ', ') FROM mijiedarbibu_dalibnieki ic JOIN kontakti c ON c.id = ic.contact_id "
        " WHERE ic.interaction_id = i.id) AS participants "
        "FROM mijiedarbibas i JOIN lietotaji u ON u.id = i.user_id WHERE i.org_id = ? ORDER BY i.date DESC, i.id DESC",
        (org_id,),
    ).fetchall()
    reqs = g.db.execute(
        f"SELECT r.*, {overdue_sql()} AS overdue FROM pieprasijumi r WHERE r.org_id = ? ORDER BY r.due_date",
        (org_id,),
    ).fetchall()
    return render_template("org_detail.html", org=org, contacts=contacts, interactions=interactions, org_requests=reqs)


def contact_form_errors(data: dict) -> dict:
    errors = {}
    if not data["name"]:
        errors["name"] = "Ievadi vārdu un uzvārdu."
    if data["email"] and not EMAIL_RE.match(data["email"]):
        errors["email"] = "E-pasta adresei jābūt formā vards@iestade.lv."
    if data["phone"] and not PHONE_RE.match(data["phone"]):
        errors["phone"] = "Tālrunim jābūt 8–15 cipariem, piemēram, +371 20001234."
    if not data["email"] and not data["phone"] and "email" not in errors:
        errors["email"] = "Norādi vismaz e-pastu vai tālruni, lai būtu iespējams sazināties."
    if data["basis"] not in CONTACT_BASES:
        errors["basis"] = "Izvēlies saziņas tiesisko pamatu."
    if not valid_date(data["basis_date"]):
        errors["basis_date"] = "Ievadi pamata datumu formātā GGGG-MM-DD."
    elif data["basis_date"] > g.today:
        errors["basis_date"] = "Pamata datums nevar būt nākotnē."
    return errors


@app.route("/organizacijas/<int:org_id>/kontakti/jauns", methods=["GET", "POST"])
@require(*STAFF)
def contact_new(org_id):
    org = get_org(org_id)
    if request.method == "GET":
        return render_template("contact_form.html", org=org, contact=None, data={"basis_date": g.today}, errors={})
    data = {k: form_value(k) for k in CONTACT_FIELDS}
    errors = contact_form_errors(data)
    if errors:
        return render_template("contact_form.html", org=org, contact=None, data=data, errors=errors), 422
    with g.db:
        cur = g.db.execute(
            "INSERT INTO kontakti (org_id, name, position, email, phone, basis, basis_date, retain_until) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (org_id, *(data[k] for k in CONTACT_FIELDS), db.retain_until(data["basis_date"])),
        )
    log_access("kontakts", cur.lastrowid, "izveidots")
    flash("Kontaktpersona pievienota.")
    return redirect(url_for("org_detail", org_id=org_id) + "#kontakti")


@app.route("/kontakti/<int:contact_id>/labot", methods=["GET", "POST"])
@require(*STAFF)
def contact_edit(contact_id):
    contact = get_contact(contact_id)
    org = get_org(contact["org_id"])
    if request.method == "GET":
        log_access("kontakts", contact_id, "atvērta labošanai")
        return render_template("contact_form.html", org=org, contact=contact, data=dict(contact), errors={})
    data = {k: form_value(k) for k in CONTACT_FIELDS}
    errors = contact_form_errors(data)
    if errors:
        return render_template("contact_form.html", org=org, contact=contact, data=data, errors=errors), 422
    changed = [k for k in CONTACT_FIELDS if data[k] != contact[k]]
    with g.db:
        g.db.execute(
            "UPDATE kontakti SET name = ?, position = ?, email = ?, phone = ?, basis = ?, basis_date = ?, "
            "retain_until = ? WHERE id = ?",
            (*(data[k] for k in CONTACT_FIELDS), db.retain_until(data["basis_date"]), contact_id),
        )
    # Žurnālā tikai mainīto lauku nosaukumi, ne vērtības.
    log_access("kontakts", contact_id, "mainīts: " + (", ".join(changed) or "bez izmaiņām"))
    flash("Kontaktpersonas dati saglabāti.")
    return redirect(url_for("org_detail", org_id=org["id"]) + "#kontakti")


# --- Darbs: F3 mijiedarbība + MI-1, F4 pieprasījumi, F5 mani uzdevumi --------

def render_interaction_form(org, data, errors, draft=None, status=200):
    contacts = g.db.execute("SELECT id, name FROM kontakti WHERE org_id = ? ORDER BY name", (org["id"],)).fetchall()
    return render_template("interaction_form.html", org=org, data=data, errors=errors,
                           contacts=contacts, draft=draft), status


@app.route("/organizacijas/<int:org_id>/mijiedarbibas/jauna", methods=["GET", "POST"])
@require(*STAFF)
def interaction_new(org_id):
    org = get_org(org_id)
    if request.method == "GET":
        return render_interaction_form(org, {"date": g.today, "type": "zvans", "contact_ids": []}, {})

    data = {k: form_value(k) for k in ("type", "date", "summary", "next_step", "notes", "ai_model", "ai_summary")}
    data["contact_ids"] = [int(c) for c in request.form.getlist("contact_ids") if c.isdigit()]

    if request.form.get("action") == "generate":
        if not data["notes"]:
            return render_interaction_form(org, data, {"notes": "Ieraksti piezīmes, no kurām veidot kopsavilkumu."}, status=422)
        draft = ai.kopsavilkums(data["notes"])
        data.update(summary=draft.summary, next_step=draft.next_step, ai_model=draft.model,
                    ai_summary=draft.summary + "\n" + draft.next_step)
        log_ai("MI-1 kopsavilkums", org_id, draft.model, "ģenerēts melnraksts")
        return render_interaction_form(org, data, {}, draft=draft)

    errors = {}
    if data["type"] not in INTERACTION_TYPES:
        errors["type"] = "Izvēlies mijiedarbības veidu."
    if not valid_date(data["date"]):
        errors["date"] = "Ievadi datumu formātā GGGG-MM-DD."
    if not data["summary"]:
        errors["summary"] = "Ieraksti kopsavilkumu."
    valid_ids = {r["id"] for r in g.db.execute("SELECT id FROM kontakti WHERE org_id = ?", (org_id,))}
    if not set(data["contact_ids"]) <= valid_ids:
        errors["contact_ids"] = "Dalībniekiem jābūt šīs organizācijas kontaktpersonām."
    if errors:
        return render_interaction_form(org, data, errors, status=422)

    ai_used = bool(data["ai_model"])
    with g.db:
        cur = g.db.execute(
            "INSERT INTO mijiedarbibas (org_id, user_id, type, date, summary, next_step, ai_generated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (org_id, g.user["id"], data["type"], data["date"], data["summary"], data["next_step"], int(ai_used)),
        )
        g.db.executemany("INSERT INTO mijiedarbibu_dalibnieki (interaction_id, contact_id) VALUES (?, ?)",
                         [(cur.lastrowid, c) for c in data["contact_ids"]])
    log_access("organizacija", org_id, "pievienota mijiedarbība")
    if ai_used:
        edited = data["summary"] + "\n" + data["next_step"] != data["ai_summary"]
        log_ai("MI-1 kopsavilkums", org_id, data["ai_model"],
               "apstiprināts ar labojumiem" if edited else "apstiprināts bez izmaiņām", cur.lastrowid)
    flash("Mijiedarbība saglabāta.")
    return redirect(url_for("org_detail", org_id=org_id))


def get_request(request_id: int) -> tuple[sqlite3.Row, sqlite3.Row]:
    req = g.db.execute("SELECT * FROM pieprasijumi WHERE id = ?", (request_id,)).fetchone()
    if req is None:
        abort(404)
    return req, get_org(req["org_id"])


@app.get("/pieprasijumi")
@require(*STAFF)
def requests_list():
    where, params = org_scope()
    rows = g.db.execute(
        f"SELECT r.*, o.name AS org_name, {overdue_sql()} AS overdue FROM pieprasijumi r "
        f"JOIN organizacijas o ON o.id = r.org_id WHERE {where} "
        f"ORDER BY overdue DESC, r.status = 'atbildets', r.due_date", params,
    ).fetchall()
    return render_template("requests.html", rows=rows)


@app.route("/organizacijas/<int:org_id>/pieprasijumi/jauns", methods=["GET", "POST"])
@require(*STAFF)
def request_new(org_id):
    org = get_org(org_id)
    default_due = (date.today() + timedelta(days=14)).isoformat()
    if request.method == "GET":
        return render_template("request_form.html", org=org, data={"due_date": default_due}, errors={})
    data = {"title": form_value("title"), "due_date": form_value("due_date")}
    errors = {}
    if not data["title"]:
        errors["title"] = "Ieraksti pieprasījuma tēmu."
    if not valid_date(data["due_date"]):
        errors["due_date"] = "Ievadi termiņu formātā GGGG-MM-DD."
    if errors:
        return render_template("request_form.html", org=org, data=data, errors=errors), 422
    with g.db:
        g.db.execute("INSERT INTO pieprasijumi (org_id, title, due_date) VALUES (?, ?, ?)",
                     (org_id, data["title"], data["due_date"]))
    flash("Pieprasījums reģistrēts ar statusu «Jauns».")
    return redirect(url_for("org_detail", org_id=org_id))


@app.post("/pieprasijumi/<int:request_id>/statuss")
@require(*STAFF)
def request_advance(request_id):
    req, _org = get_request(request_id)
    new_status = NEXT_STATUS.get(req["status"])
    if new_status is None or request.form.get("status") != new_status:
        abort(409)
    with g.db:
        g.db.execute("UPDATE pieprasijumi SET status = ? WHERE id = ?", (new_status, request_id))
    flash(f"Statuss mainīts uz «{REQUEST_STATUSES[new_status]}».")
    return redirect(safe_next(url_for("requests_list")))


@app.route("/pieprasijumi/<int:request_id>/atbilde", methods=["GET", "POST"])
@require(*STAFF)
def request_reply(request_id):
    """COULD: e-pasta atbildes projekts. Sistēma e-pastu nesūta — cilvēks nokopē, pārbauda un nosūta pats."""
    req, org = get_request(request_id)
    data, errors, draft = {"notes": form_value("notes")}, {}, None
    if request.method == "POST":
        if request.form.get("action") == "sent":
            log_ai("E-pasta atbildes projekts", org["id"], form_value("ai_model") or "—", "cilvēks nosūtīja")
            flash("Atzīmēts, ka atbildi nosūtīji. Ja jautājums atrisināts, maini pieprasījuma statusu.")
            return redirect(url_for("requests_list"))
        if not data["notes"]:
            errors["notes"] = "Ieraksti iekšējās piezīmes — ko atbildēt."
        else:
            draft = ai.atbildes_projekts(req["title"], data["notes"])
            log_ai("E-pasta atbildes projekts", org["id"], draft.model, "ģenerēts melnraksts")
    status = 422 if errors else 200
    return render_template("request_reply.html", req=req, org=org, data=data, errors=errors, draft=draft), status


@app.route("/uzdevumi", methods=["GET", "POST"])
@require(*STAFF)
def tasks():
    where, params = org_scope()
    orgs_ = g.db.execute(f"SELECT o.id, o.name FROM organizacijas o WHERE {where} ORDER BY o.name", params).fetchall()
    reqs = g.db.execute(
        f"SELECT r.id, r.title, o.name AS org_name FROM pieprasijumi r JOIN organizacijas o ON o.id = r.org_id "
        f"WHERE r.status != 'atbildets' AND {where} ORDER BY r.title", params,
    ).fetchall()
    data, errors, status = {"due_date": g.today}, {}, 200
    if request.method == "POST":
        data = {"title": form_value("title"), "due_date": form_value("due_date"), "link": form_value("link")}
        if not data["title"]:
            errors["title"] = "Ieraksti uzdevumu."
        if not valid_date(data["due_date"]):
            errors["due_date"] = "Ievadi termiņu formātā GGGG-MM-DD."
        kind, _, ref = data["link"].partition(":")
        org_id = int(ref) if kind == "org" and ref.isdigit() and int(ref) in {o["id"] for o in orgs_} else None
        req_id = int(ref) if kind == "req" and ref.isdigit() and int(ref) in {r["id"] for r in reqs} else None
        if org_id is None and req_id is None:
            errors["link"] = "Sasaisti uzdevumu ar organizāciju vai pieprasījumu."
        if not errors:
            with g.db:
                g.db.execute("INSERT INTO uzdevumi (user_id, title, due_date, org_id, request_id) VALUES (?, ?, ?, ?, ?)",
                             (g.user["id"], data["title"], data["due_date"], org_id, req_id))
            flash("Uzdevums pievienots.")
            return redirect(url_for("tasks"))
        status = 422
    upcoming = g.db.execute(
        "SELECT t.*, o.name AS org_name, r.title AS request_title FROM uzdevumi t "
        "LEFT JOIN organizacijas o ON o.id = t.org_id LEFT JOIN pieprasijumi r ON r.id = t.request_id "
        "WHERE t.user_id = ? AND t.done = 0 AND t.due_date > date('now', 'localtime') ORDER BY t.due_date",
        (g.user["id"],),
    ).fetchall()
    return render_template("tasks.html", today_tasks=todays_tasks(), upcoming=upcoming, orgs=orgs_,
                           reqs=reqs, data=data, errors=errors), status


@app.post("/uzdevumi/<int:task_id>/izpildits")
@require(*STAFF)
def task_done(task_id):
    with g.db:
        cur = g.db.execute("UPDATE uzdevumi SET done = 1 WHERE id = ? AND user_id = ?", (task_id, g.user["id"]))
    if cur.rowcount == 0:
        abort(404)
    flash("Uzdevums atzīmēts kā izpildīts.")
    return redirect(safe_next(url_for("tasks")))


# --- Vadība: F7 pārskats -------------------------------------------------------

@app.get("/parskats")
@require("vaditajs")
def overview():
    activity = g.db.execute(
        "SELECT u.name, COUNT(i.id) AS n FROM lietotaji u LEFT JOIN mijiedarbibas i ON i.user_id = u.id "
        "AND i.date >= date('now', 'localtime', '-30 days') WHERE u.role = 'darbinieks' "
        "GROUP BY u.id ORDER BY n DESC, u.name"
    ).fetchall()
    overdue = g.db.execute(
        f"SELECT r.*, o.name AS org_name, u.name AS owner_name FROM pieprasijumi r "
        f"JOIN organizacijas o ON o.id = r.org_id JOIN lietotaji u ON u.id = o.owner_id "
        f"WHERE {overdue_sql()} ORDER BY r.due_date"
    ).fetchall()
    top_orgs = g.db.execute(
        "SELECT o.id, o.name, COUNT(i.id) AS n, MAX(i.date) AS last FROM organizacijas o "
        "JOIN mijiedarbibas i ON i.org_id = o.id AND i.date >= date('now', 'localtime', '-90 days') "
        "GROUP BY o.id ORDER BY n DESC, last DESC LIMIT 5"
    ).fetchall()
    max_n = max([a["n"] for a in activity] + [1])
    return render_template("overview.html", activity=activity, overdue=overdue, top_orgs=top_orgs, max_n=max_n)


# --- Administrators: lomas, dzēšana, piekļuves žurnāls (N2, N3) ---------------

@app.get("/administresana")
@require("administrators")
def admin():
    q = request.args.get("q", "").strip()
    expired_only = request.args.get("beigusies") == "1"
    contacts = None
    if q or expired_only:
        # Minimāli dati dzēšanas pieprasījuma izpildei: vārds, organizācija, glabāšanas termiņš.
        sql = ("SELECT c.id, c.name, c.retain_until, o.name AS org_name FROM kontakti c "
               "JOIN organizacijas o ON o.id = c.org_id WHERE 1 = 1")
        params: tuple = ()
        if q:
            sql += " AND c.name LIKE ?"
            params = (f"%{q}%",)
        if expired_only:
            sql += " AND c.retain_until < date('now', 'localtime')"
        contacts = g.db.execute(sql + " ORDER BY c.retain_until", params).fetchall()
    users = g.db.execute("SELECT * FROM lietotaji ORDER BY id").fetchall()
    expired_count = g.db.execute(
        "SELECT COUNT(*) FROM kontakti WHERE retain_until < date('now', 'localtime')").fetchone()[0]
    log = g.db.execute(
        "SELECT a.*, u.name AS user_name, o.name AS org_name FROM piekluves_zurnals a "
        "JOIN lietotaji u ON u.id = a.user_id "
        "LEFT JOIN organizacijas o ON a.entity = 'organizacija' AND o.id = a.entity_id "
        "ORDER BY a.id DESC LIMIT 50"
    ).fetchall()
    ai_rows = g.db.execute(
        "SELECT m.*, u.name AS user_name, o.name AS org_name FROM mi_zurnals m JOIN lietotaji u ON u.id = m.user_id "
        "LEFT JOIN organizacijas o ON o.id = m.org_id ORDER BY m.id DESC LIMIT 50"
    ).fetchall()
    return render_template("admin.html", q=q, expired_only=expired_only, contacts=contacts, users=users,
                           expired_count=expired_count, log=log, ai_rows=ai_rows)


@app.post("/administresana/lomas")
@require("administrators")
def admin_role():
    user = g.db.execute("SELECT * FROM lietotaji WHERE id = ?", (request.form.get("user_id", type=int),)).fetchone()
    role = form_value("role")
    if user is None or role not in ROLES:
        abort(400)
    admins = g.db.execute("SELECT COUNT(*) FROM lietotaji WHERE role = 'administrators'").fetchone()[0]
    if user["role"] == "administrators" and role != "administrators" and admins == 1:
        flash("Nevar noņemt pēdējo administratoru.", "error")
        return redirect(url_for("admin"))
    if role != user["role"]:
        with g.db:
            g.db.execute("UPDATE lietotaji SET role = ? WHERE id = ?", (role, user["id"]))
        log_access("lietotajs", user["id"], f"loma mainīta: {user['role']} → {role}")
        flash(f"{user['name']}: loma mainīta uz «{ROLES[role]}».")
    return redirect(url_for("admin"))


@app.post("/administresana/kontakti/<int:contact_id>/dzest")
@require("administrators")
def admin_contact_delete(contact_id):
    if g.db.execute("SELECT 1 FROM kontakti WHERE id = ?", (contact_id,)).fetchone() is None:
        abort(404)
    if request.form.get("confirm") != "1":
        flash("Dzēšana nav apstiprināta — atzīmē apstiprinājuma lauku.", "error")
        return redirect(url_for("admin", q=form_value("q")))
    with g.db:
        g.db.execute("DELETE FROM kontakti WHERE id = ?", (contact_id,))
    log_access("kontakts", contact_id, "dzēsts pēc pieprasījuma")
    flash("Kontaktpersonas dati dzēsti. Žurnālā saglabāts tikai dzēšanas fakts un ID.")
    return redirect(url_for("admin"))


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", title="Nav piekļuves",
                           message="Šī sadaļa nav pieejama tavai lomai."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", title="Nav atrasts",
                           message="Ieraksts neeksistē vai nav tavā atbildībā."), 404


if __name__ == "__main__":
    app.run(debug=True)
