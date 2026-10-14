from datetime import date
from html.parser import HTMLParser

import pytest

pytest.importorskip("flask")

import ai  # noqa: E402
import app as crm  # noqa: E402
import db as crm_db  # noqa: E402

ANNA, JANIS, VADITAJS, ADMIN = 1, 2, 4, 5  # sēklas datu lietotāji
ANNA_ORG, JANIS_ORG = 1, 4


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(crm_db, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CRM_AI_OFFLINE", "1")
    crm.app.config.update(TESTING=True, _db_ready=False)
    with crm.app.test_client() as c:
        with c.session_transaction() as s:
            s["csrf"] = "t"
        yield c


def login(client, user_id):
    return client.post("/sakums", data={"user_id": user_id, "csrf": "t"})


def post(client, url, **data):
    return client.post(url, data={"csrf": "t", **data})


def db():
    return crm_db.connect()


def access_log(entity, entity_id):
    return [r[0] for r in db().execute(
        "SELECT action FROM piekluves_zurnals WHERE entity = ? AND entity_id = ? ORDER BY id", (entity, entity_id))]


# --- N4 sēklas dati, N3 lomas -------------------------------------------------

def test_seed_counts(client):
    client.get("/sakums")
    conn = db()
    counts = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("organizacijas", "kontakti", "mijiedarbibas")]
    assert counts == [10, 20, 30]


def test_anonymous_redirected_to_role_choice(client):
    response = client.get("/")
    assert response.status_code == 302 and response.headers["Location"].endswith("/sakums")


def test_post_without_csrf_rejected(client):
    assert client.post("/sakums", data={"user_id": ANNA}).status_code == 400


def test_employee_sees_only_own_orgs(client):
    login(client, ANNA)
    page = client.get("/organizacijas").get_data(as_text=True)
    assert "SIA Ezermalas Koks" in page and "Ezermalas novada pašvaldība" not in page
    assert client.get(f"/organizacijas/{JANIS_ORG}").status_code == 404


def test_manager_sees_all_and_overview(client):
    login(client, VADITAJS)
    assert client.get(f"/organizacijas/{JANIS_ORG}").status_code == 200
    page = client.get("/parskats").get_data(as_text=True)
    assert "<svg" in page and "Mijiedarbības pa darbiniekiem" in page


@pytest.mark.parametrize("user, url", [
    (ANNA, "/parskats"), (ANNA, "/administresana"), (VADITAJS, "/administresana"),
    (ADMIN, "/organizacijas"), (ADMIN, f"/organizacijas/{ANNA_ORG}"), (ADMIN, "/parskats"), (ADMIN, "/uzdevumi"),
])
def test_role_boundaries(client, user, url):
    login(client, user)
    assert client.get(url).status_code == 403


def test_admin_lands_on_admin_screen(client):
    login(client, ADMIN)
    response = client.get("/")
    assert response.headers["Location"].endswith("/administresana")


def test_admin_changes_role_and_keeps_last_admin(client):
    login(client, ADMIN)
    post(client, "/administresana/lomas", user_id=ANNA, role="vaditajs")
    assert db().execute("SELECT role FROM lietotaji WHERE id = ?", (ANNA,)).fetchone()[0] == "vaditajs"
    assert access_log("lietotajs", ANNA) == ["loma mainīta: darbinieks → vaditajs"]
    post(client, "/administresana/lomas", user_id=ADMIN, role="darbinieks")
    assert db().execute("SELECT role FROM lietotaji WHERE id = ?", (ADMIN,)).fetchone()[0] == "administrators"


# --- F9 sākums ---------------------------------------------------------------

def test_dashboard_after_login(client):
    response = login(client, ANNA)
    assert response.headers["Location"].endswith("/")
    page = client.get("/").get_data(as_text=True)
    assert "Mani uzdevumi šodien" in page and "Piezvanīt par semināra datumu" in page


# --- F1 organizācijas --------------------------------------------------------

def test_create_org_and_search(client):
    login(client, ANNA)
    response = post(client, "/organizacijas/jauna", name="SIA Jauna", reg_nr="40003999999", type="uznemums")
    assert response.status_code == 302
    assert "SIA Jauna" in client.get("/organizacijas?q=Jauna").get_data(as_text=True)


@pytest.mark.parametrize("data, message", [
    ({"name": "", "reg_nr": "40003999999", "type": "nvo"}, "Ievadi organizācijas nosaukumu"),
    ({"name": "X", "reg_nr": "123", "type": "nvo"}, "11 cipariem"),
    ({"name": "X", "reg_nr": "40003000001", "type": "nvo"}, "jau ir sistēmā"),
    ({"name": "X", "reg_nr": "40003999999", "type": "cits"}, "Izvēlies organizācijas veidu"),
])
def test_org_validation_errors_as_text(client, data, message):
    login(client, ANNA)
    response = post(client, "/organizacijas/jauna", **data)
    page = response.get_data(as_text=True)
    assert response.status_code == 422
    assert message in page and 'aria-invalid="true"' in page and 'role="alert"' in page


def test_employee_cannot_reassign_org(client):
    login(client, ANNA)
    post(client, f"/organizacijas/{ANNA_ORG}/labot", name="SIA Ezermalas Koks", reg_nr="40003000001",
         type="uznemums", owner_id=JANIS)
    assert db().execute("SELECT owner_id FROM organizacijas WHERE id = ?", (ANNA_ORG,)).fetchone()[0] == ANNA


def test_org_card_shows_contacts_and_logs_view(client):
    login(client, ANNA)
    page = client.get(f"/organizacijas/{ANNA_ORG}").get_data(as_text=True)
    assert "Ilze Liepa" in page and "ilze@piemers.lv" in page
    assert access_log("organizacija", ANNA_ORG) == ["skatīta kartīte (2 kontakti)"]


# --- F2 kontaktpersonas, N2 VDAR ---------------------------------------------

def test_contact_requires_email_or_phone(client):
    login(client, ANNA)
    response = post(client, f"/organizacijas/{ANNA_ORG}/kontakti/jauns", name="Test Persona",
                    basis="ligums", basis_date=date.today().isoformat())
    assert response.status_code == 422
    assert "vismaz e-pastu vai tālruni" in response.get_data(as_text=True)


def test_contact_create_edit_retention_and_log(client):
    login(client, ANNA)
    post(client, f"/organizacijas/{ANNA_ORG}/kontakti/jauns", name="Test Persona", email="t@piemers.lv",
         basis="piekrisana", basis_date="2025-01-15")
    contact = db().execute("SELECT * FROM kontakti WHERE name = 'Test Persona'").fetchone()
    assert contact["retain_until"] == "2028-01-15"
    post(client, f"/kontakti/{contact['id']}/labot", name="Test Persona", position="Jurists",
         email="t@piemers.lv", phone="", basis="piekrisana", basis_date="2026-01-10")
    contact = db().execute("SELECT * FROM kontakti WHERE id = ?", (contact["id"],)).fetchone()
    assert contact["retain_until"] == "2029-01-10" and contact["position"] == "Jurists"
    assert access_log("kontakts", contact["id"]) == ["izveidots", "mainīts: position, basis_date"]


def test_employee_cannot_delete_contact(client):
    login(client, ANNA)
    assert post(client, "/administresana/kontakti/1/dzest", confirm="1").status_code == 403
    assert db().execute("SELECT 1 FROM kontakti WHERE id = 1").fetchone() is not None


def test_admin_deletes_contact_on_request(client):
    login(client, ADMIN)
    assert "Ilze Liepa" in client.get("/administresana?q=Ilze").get_data(as_text=True)
    post(client, "/administresana/kontakti/1/dzest")  # bez apstiprinājuma — nedzēš
    assert db().execute("SELECT 1 FROM kontakti WHERE id = 1").fetchone() is not None
    post(client, "/administresana/kontakti/1/dzest", confirm="1")
    conn = db()
    assert conn.execute("SELECT 1 FROM kontakti WHERE id = 1").fetchone() is None
    assert conn.execute("SELECT 1 FROM mijiedarbibu_dalibnieki WHERE contact_id = 1").fetchone() is None
    assert access_log("kontakts", 1) == ["dzēsts pēc pieprasījuma"]


def test_admin_sees_expired_contacts_and_access_log(client):
    login(client, ANNA)
    client.get(f"/organizacijas/{ANNA_ORG}")
    client.post("/iziet", data={"csrf": "t"})
    with client.session_transaction() as s:
        s["csrf"] = "t"
    login(client, ADMIN)
    page = client.get("/administresana?beigusies=1").get_data(as_text=True)
    assert "Termiņš beidzies" in page and "Inese Celma" in page
    assert "skatīta kartīte" in page and "Anna Ozola" in page


def test_employee_cannot_edit_foreign_contact(client):
    login(client, ANNA)
    foreign = db().execute("SELECT id FROM kontakti WHERE org_id = ?", (JANIS_ORG,)).fetchone()[0]
    assert client.get(f"/kontakti/{foreign}/labot").status_code == 404


# --- F3 mijiedarbības, MI-1 --------------------------------------------------

def test_interactions_chronological(client):
    login(client, ANNA)
    post(client, f"/organizacijas/{ANNA_ORG}/mijiedarbibas/jauna", type="sanaksme",
         date=date.today().isoformat(), summary="Jaunākā tikšanās", contact_ids="1")
    page = client.get(f"/organizacijas/{ANNA_ORG}").get_data(as_text=True)
    timeline = page[page.index("Mijiedarbību žurnāls"):]
    assert timeline.index("Jaunākā tikšanās") < timeline.index("Konsultācija par ES fondu")
    assert "pievienota mijiedarbība" in access_log("organizacija", ANNA_ORG)


def test_interaction_rejects_foreign_contact(client):
    login(client, ANNA)
    response = post(client, f"/organizacijas/{ANNA_ORG}/mijiedarbibas/jauna", type="zvans",
                    date=date.today().isoformat(), summary="X", contact_ids="7")
    assert response.status_code == 422


def test_ai_summary_is_draft_until_confirmed(client):
    login(client, ANNA)
    notes = ("Zvanīja Ilze, e-pasts ilze@piemers.lv. Interesējās par semināru. Viņi vēlas 10 vietas. "
             "Budžets vēl nav apstiprināts. Vienojāmies, ka nosūtīšu programmu līdz piektdienai.")
    response = post(client, f"/organizacijas/{ANNA_ORG}/mijiedarbibas/jauna", action="generate",
                    type="zvans", date=date.today().isoformat(), notes=notes)
    page = response.get_data(as_text=True)
    assert "Ģenerēts ar MI" in page and "ilze@piemers.lv" not in page.split("Kopsavilkums")[1]
    assert db().execute("SELECT COUNT(*) FROM mijiedarbibas").fetchone()[0] == 30  # melnraksts netiek saglabāts
    assert [r[0] for r in db().execute("SELECT outcome FROM mi_zurnals")] == ["ģenerēts melnraksts"]

    draft = ai.kopsavilkums(notes)
    post(client, f"/organizacijas/{ANNA_ORG}/mijiedarbibas/jauna", action="save", type="zvans",
         date=date.today().isoformat(), summary=draft.summary + " Labots.", next_step=draft.next_step,
         ai_model=draft.model, ai_summary=draft.summary + "\n" + draft.next_step)
    conn = db()
    assert conn.execute("SELECT ai_generated FROM mijiedarbibas ORDER BY id DESC").fetchone()[0] == 1
    assert conn.execute("SELECT outcome FROM mi_zurnals ORDER BY id DESC").fetchone()[0] == "apstiprināts ar labojumiem"


def test_offline_summary_contract_three_sentences_and_redacts():
    draft = ai.kopsavilkums("Pirmais. Otrais teikums, tālr. +371 2000 1234. Trešais. Ceturtais. Jāsagatavo atbilde.")
    assert draft.summary.count(".") == 3 and "2000 1234" not in draft.summary
    assert draft.next_step == "Jāsagatavo atbilde."
    assert draft.model == ai.OFFLINE_MODEL


# --- F4 pieprasījumi, e-pasta atbildes projekts (COULD) ----------------------

def test_overdue_marked_with_text(client):
    login(client, ANNA)
    page = client.get("/pieprasijumi").get_data(as_text=True)
    assert "Kavēts" in page


def test_request_status_only_forward(client):
    login(client, ANNA)
    assert post(client, "/pieprasijumi/1/statuss", status="atbildets").status_code == 409
    assert post(client, "/pieprasijumi/1/statuss", status="darba").status_code == 302
    assert db().execute("SELECT status FROM pieprasijumi WHERE id = 1").fetchone()[0] == "darba"


def test_open_redirect_blocked(client):
    login(client, ANNA)
    response = post(client, "/pieprasijumi/1/statuss", status="darba", next="//evil.example")
    assert response.headers["Location"].endswith("/pieprasijumi")


def test_reply_draft_marked_and_human_sends(client):
    login(client, ANNA)
    assert post(client, "/pieprasijumi/1/atbilde", action="generate", notes="").status_code == 422
    page = post(client, "/pieprasijumi/1/atbilde", action="generate",
                notes="Būvatļauja nav vajadzīga nojumei līdz 25 m². Zvanīt 2000 1234.").get_data(as_text=True)
    draft = page[page.index('id="f-draft"'):]
    assert "Ģenerēts ar MI" in page and "Konsultācija par būvatļauju" in draft and "2000 1234" not in draft
    post(client, "/pieprasijumi/1/atbilde", action="sent", ai_model=ai.OFFLINE_MODEL)
    outcomes = [r[0] for r in db().execute("SELECT outcome FROM mi_zurnals ORDER BY id")]
    assert outcomes == ["ģenerēts melnraksts", "cilvēks nosūtīja"]


def test_reply_for_foreign_request_hidden(client):
    login(client, ANNA)
    assert client.get("/pieprasijumi/4/atbilde").status_code == 404


# --- F5 uzdevumi -------------------------------------------------------------

def test_task_create_requires_link_and_mark_done(client):
    login(client, ANNA)
    today = date.today().isoformat()
    assert post(client, "/uzdevumi", title="Bez saites", due_date=today, link="").status_code == 422
    assert post(client, "/uzdevumi", title="Svešs", due_date=today, link=f"org:{JANIS_ORG}").status_code == 422
    post(client, "/uzdevumi", title="Jauns uzdevums", due_date=today, link=f"org:{ANNA_ORG}")
    task_id = db().execute("SELECT id FROM uzdevumi WHERE title = 'Jauns uzdevums'").fetchone()[0]
    assert "Jauns uzdevums" in client.get("/").get_data(as_text=True)
    post(client, f"/uzdevumi/{task_id}/izpildits")
    assert "Jauns uzdevums" not in client.get("/").get_data(as_text=True)


def test_cannot_complete_foreign_task(client):
    login(client, ANNA)
    janis_task = db().execute("SELECT id FROM uzdevumi WHERE user_id = ?", (JANIS,)).fetchone()[0]
    assert post(client, f"/uzdevumi/{janis_task}/izpildits").status_code == 404


# --- F6 meklēšana (organizāciju saraksta ekrānā) -----------------------------

def test_search_across_entities_respects_scope(client):
    login(client, ANNA)
    page = client.get("/organizacijas?q=Ezermalas").get_data(as_text=True)
    assert "SIA Ezermalas Koks" in page and "Ezermalas novada pašvaldība" not in page
    assert "Ilze Liepa" in client.get("/organizacijas?q=Ilze").get_data(as_text=True)
    assert "Konsultācija par būvatļauju" in client.get("/organizacijas?q=būvatļauju").get_data(as_text=True)


# --- N1 automatizētās piekļūstamības pārbaudes (statiskās; pārlūkā — a11y_check.py)

class A11yParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.labels_for, self.controls, self.problems = [], set(), [], []
        self.lang = None
        self.h1 = 0
        self.caption_in_table, self.th_without_scope = [], 0
        self.landmarks = set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag in ("main", "nav", "header", "footer"):
            self.landmarks.add(tag)
        if tag == "label" and "for" in a:
            self.labels_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit"):
            self.controls.append(a.get("id"))
        if tag == "img" and "alt" not in a:
            self.problems.append("img bez alt")
        if tag == "table":
            self.caption_in_table.append(False)
        if tag == "caption" and self.caption_in_table:
            self.caption_in_table[-1] = True
        if tag == "th" and "scope" not in a:
            self.th_without_scope += 1
        if tag == "button" and a.get("type") is None:
            self.problems.append("button bez type")

    def handle_endtag(self, tag):
        if tag == "table" and not self.caption_in_table.pop():
            self.problems.append("tabula bez caption")


A11Y_PAGES = [
    (ANNA, "/"), (ANNA, "/organizacijas?q=a"), (ANNA, "/organizacijas/jauna"), (ANNA, f"/organizacijas/{ANNA_ORG}"),
    (ANNA, f"/organizacijas/{ANNA_ORG}/kontakti/jauns"), (ANNA, "/kontakti/1/labot"),
    (ANNA, f"/organizacijas/{ANNA_ORG}/mijiedarbibas/jauna"), (ANNA, "/pieprasijumi"), (ANNA, "/pieprasijumi/1/atbilde"),
    (ANNA, f"/organizacijas/{ANNA_ORG}/pieprasijumi/jauns"), (ANNA, "/uzdevumi"),
    (VADITAJS, "/parskats"), (ADMIN, "/administresana?beigusies=1"), (None, "/pieklustamiba"), (None, "/sakums"),
]


@pytest.mark.parametrize("user, url", A11Y_PAGES)
def test_a11y_static_checks(client, user, url):
    if user:
        login(client, user)
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    p = A11yParser()
    p.feed(html)
    assert p.lang == "lv"
    assert p.h1 == 1, "katrā lapā tieši viens h1"
    assert {"main", "footer"} <= p.landmarks
    assert len(p.ids) == len(set(p.ids)), "dublēti id"
    unlabeled = [c for c in p.controls if c not in p.labels_for]
    assert not unlabeled, f"lauki bez label: {unlabeled}"
    assert p.th_without_scope == 0
    assert not p.problems
    assert 'class="skip" href="#saturs"' in html
    assert 'href="/pieklustamiba"' in html
