"""Datu slānis: SQLite data.db, shēma un sintētiskie sākumdati (N4: 10 organizācijas, 20 kontakti, 30 mijiedarbības)."""

import os
import sqlite3
from datetime import date, timedelta

DB_PATH = os.environ.get("CRM_DB", os.path.join(os.path.dirname(__file__), "data.db"))

ROLES = {"darbinieks": "Darbinieks", "vaditajs": "Vadītājs", "administrators": "Administrators"}
ORG_TYPES = {"uznemums": "Uzņēmums", "nvo": "NVO", "pasvaldiba": "Pašvaldība"}
INTERACTION_TYPES = {"zvans": "Zvans", "epasts": "E-pasts", "sanaksme": "Sanāksme"}
REQUEST_STATUSES = {"jauns": "Jauns", "darba": "Darbā", "atbildets": "Atbildēts"}
NEXT_STATUS = {"jauns": "darba", "darba": "atbildets"}
# N2: saziņas tiesiskais pamats kontaktpersonai
CONTACT_BASES = {
    "ligums": "Līgums ar organizāciju",
    "legitimas_intereses": "Leģitīmās intereses",
    "piekrisana": "Piekrišana",
}
RETENTION_YEARS = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS lietotaji (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('darbinieks', 'vaditajs', 'administrators'))
);
CREATE TABLE IF NOT EXISTS organizacijas (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    reg_nr TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES lietotaji(id)
);
CREATE TABLE IF NOT EXISTS kontakti (
    id INTEGER PRIMARY KEY,
    org_id INTEGER NOT NULL REFERENCES organizacijas(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    basis TEXT NOT NULL,
    basis_date TEXT NOT NULL,
    retain_until TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mijiedarbibas (
    id INTEGER PRIMARY KEY,
    org_id INTEGER NOT NULL REFERENCES organizacijas(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES lietotaji(id),
    type TEXT NOT NULL,
    date TEXT NOT NULL,
    summary TEXT NOT NULL,
    next_step TEXT NOT NULL DEFAULT '',
    ai_generated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mijiedarbibu_dalibnieki (
    interaction_id INTEGER NOT NULL REFERENCES mijiedarbibas(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES kontakti(id) ON DELETE CASCADE,
    PRIMARY KEY (interaction_id, contact_id)
);
CREATE TABLE IF NOT EXISTS pieprasijumi (
    id INTEGER PRIMARY KEY,
    org_id INTEGER NOT NULL REFERENCES organizacijas(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'jauns',
    due_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (date('now'))
);
CREATE TABLE IF NOT EXISTS uzdevumi (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES lietotaji(id),
    title TEXT NOT NULL,
    due_date TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    org_id INTEGER REFERENCES organizacijas(id) ON DELETE CASCADE,
    request_id INTEGER REFERENCES pieprasijumi(id) ON DELETE CASCADE,
    CHECK (org_id IS NOT NULL OR request_id IS NOT NULL)
);
-- N2: kas (user_id), ko (entity + entity_id), kad (at) skatīja vai mainīja. Tikai ID, bez personas datiem.
CREATE TABLE IF NOT EXISTS piekluves_zurnals (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES lietotaji(id),
    entity TEXT NOT NULL CHECK (entity IN ('organizacija', 'kontakts', 'lietotajs')),
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- MI-1 un e-pasta atbildes projekts: katrs ģenerējums un cilvēka lēmums
CREATE TABLE IF NOT EXISTS mi_zurnals (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES lietotaji(id),
    component TEXT NOT NULL,
    org_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    outcome TEXT NOT NULL,
    interaction_id INTEGER,
    at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def retain_until(basis_date: str) -> str:
    start = date.fromisoformat(basis_date)
    try:
        return start.replace(year=start.year + RETENTION_YEARS).isoformat()
    except ValueError:  # 29. februāris
        return start.replace(year=start.year + RETENTION_YEARS, day=28).isoformat()


def init_db(seed: bool = True) -> None:
    conn = connect()
    try:
        with conn:
            conn.executescript(SCHEMA)
            if seed and conn.execute("SELECT COUNT(*) FROM lietotaji").fetchone()[0] == 0:
                seed_data(conn)
    finally:
        conn.close()


# --- Sintētiskie sākumdati ---------------------------------------------------

USERS = [
    ("Anna Ozola", "darbinieks"),
    ("Jānis Bērziņš", "darbinieks"),
    ("Līga Kalniņa", "darbinieks"),
    ("Mārtiņš Vītols", "vaditajs"),
    ("Rasma Priede", "administrators"),
]

ORGS = [
    ("SIA Ezermalas Koks", "40003000001", "uznemums", 1),
    ("SIA Zaļā Enerģija", "40003000002", "uznemums", 1),
    ("Biedrība «Kopā Ezermalā»", "40008000003", "nvo", 1),
    ("Ezermalas novada pašvaldība", "90000000004", "pasvaldiba", 2),
    ("SIA Datu Darbnīca", "40003000005", "uznemums", 2),
    ("Nodibinājums «Jaunatnei»", "40008000006", "nvo", 2),
    ("Priedaines pagasta pārvalde", "90000000007", "pasvaldiba", 3),
    ("SIA Lauku Maize", "40003000008", "uznemums", 3),
    ("Biedrība «Zaļais Krasts»", "40008000009", "nvo", 3),
    ("AS Ezermalas Ūdens", "40003000010", "uznemums", 1),
]

CONTACT_NAMES = [
    ("Ilze Liepa", "Valdes locekle"), ("Raivis Krūmiņš", "Projektu vadītājs"),
    ("Dace Sproģe", "Valdes priekšsēdētāja"), ("Edgars Lācis", "Brīvprātīgo koordinators"),
    ("Inese Celma", "Attīstības nodaļas vadītāja"), ("Kārlis Rozītis", "Juriskonsults"),
    ("Sanita Bite", "Izpilddirektore"), ("Normunds Egle", "IT vadītājs"),
    ("Zane Akmene", "Programmu vadītāja"), ("Uldis Strauts", "Grāmatvedis"),
    ("Agnese Kļava", "Pārvaldes vadītāja"), ("Roberts Dzenis", "Speciālists"),
    ("Laura Pūce", "Īpašniece"), ("Gints Vējš", "Ražošanas vadītājs"),
    ("Evija Rasa", "Valdes locekle"), ("Toms Sīlis", "Koordinators"),
    ("Kristīne Lapa", "Valdes priekšsēdētāja"), ("Pēteris Saulītis", "Tehniskais direktors"),
    ("Marta Ziediņa", "Klientu attiecību vadītāja"), ("Andris Kalns", "Valdes loceklis"),
]

SUMMARIES = [
    ("Konsultācija par ES fondu atbalsta pieteikumu.", "Nosūtīt pieteikuma veidni."),
    ("Apspriesta dalība pavasara seminārā.", "Apstiprināt dalībnieku skaitu."),
    ("Saņemts jautājums par atļauju termiņiem.", "Sagatavot rakstisku atbildi."),
    ("Ikgadējā sadarbības sanāksme, pārrunāti plāni.", "Nosūtīt sanāksmes protokolu."),
    ("Precizēti iesniegtā pieprasījuma dati.", "Pārbaudīt reģistra datus."),
    ("Ievadsaruna ar jauno kontaktpersonu.", "Uzaicināt uz nākamo semināru."),
]


def seed_data(conn: sqlite3.Connection) -> None:
    today = date.today()
    conn.executemany("INSERT INTO lietotaji (name, role) VALUES (?, ?)", USERS)
    conn.executemany("INSERT INTO organizacijas (name, reg_nr, type, owner_id) VALUES (?, ?, ?, ?)", ORGS)

    bases = list(CONTACT_BASES)
    for i, (name, position) in enumerate(CONTACT_NAMES):
        org_id = i // 2 + 1
        # Divi kontakti ar pagājušu glabāšanas termiņu, lai N2 pārskats nav tukšs.
        basis_date = (today - timedelta(days=365 * 3 + 30 if i in (4, 13) else 40 * i + 10)).isoformat()
        login = name.split()[0].lower().translate(str.maketrans("āčēģīķļņšūž", "acegiklnsuz"))
        conn.execute(
            "INSERT INTO kontakti (org_id, name, position, email, phone, basis, basis_date, retain_until) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (org_id, name, position, f"{login}@piemers.lv", f"+371 2000 {1000 + i}",
             bases[i % 3], basis_date, retain_until(basis_date)),
        )

    types = list(INTERACTION_TYPES)
    for i in range(30):
        org_id = i % 10 + 1
        owner = ORGS[org_id - 1][3]
        summary, next_step = SUMMARIES[i % len(SUMMARIES)]
        cur = conn.execute(
            "INSERT INTO mijiedarbibas (org_id, user_id, type, date, summary, next_step) VALUES (?, ?, ?, ?, ?, ?)",
            (org_id, owner, types[i % 3], (today - timedelta(days=i * 3 + 1)).isoformat(), summary, next_step),
        )
        conn.execute(
            "INSERT INTO mijiedarbibu_dalibnieki (interaction_id, contact_id) VALUES (?, ?)",
            (cur.lastrowid, (org_id - 1) * 2 + 1 + i % 2),
        )

    requests = [
        (1, "Konsultācija par būvatļauju", "jauns", 5),
        (2, "Informācija par atbalsta programmu", "darba", -3),
        (3, "Telpas semināram", "atbildets", -10),
        (4, "Datu apmaiņas līgums", "darba", 10),
        (5, "Atvērto datu pieejamība", "jauns", -1),
        (7, "Ceļu remonta plāns", "jauns", 14),
        (8, "Tirdziņa atļauja", "darba", 2),
        (9, "Krasta sakopšanas talka", "jauns", -5),
    ]
    for org_id, title, status, days in requests:
        conn.execute(
            "INSERT INTO pieprasijumi (org_id, title, status, due_date, created_at) VALUES (?, ?, ?, ?, ?)",
            (org_id, title, status, (today + timedelta(days=days)).isoformat(),
             (today - timedelta(days=20)).isoformat()),
        )

    tasks = [
        (1, "Piezvanīt par semināra datumu", 0, 1, None),
        (1, "Atbildēt uz būvatļaujas jautājumu", -1, None, 1),
        (2, "Sagatavot līguma projektu", 0, None, 4),
        (2, "Pārbaudīt atvērto datu sarakstu", 3, 5, None),
        (3, "Nosūtīt talkas plānu", 0, None, 8),
        (3, "Satikties ar maizes ceptuvi", 7, 8, None),
    ]
    for user_id, title, days, org_id, request_id in tasks:
        conn.execute(
            "INSERT INTO uzdevumi (user_id, title, due_date, org_id, request_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, (today + timedelta(days=days)).isoformat(), org_id, request_id),
        )


if __name__ == "__main__":
    init_db()
    print(f"Datubāze gatava: {DB_PATH}")
