"""N1 piekļūstamības pārbaude pārlūkā: axe-core + Playwright, pārplūde 200 %/400 %, tastatūras ceļš.

Palaišana (no mapes sandbox/crm):
    pip install playwright && python -m playwright install chromium
    python tests/a11y_check.py

axe-core tiek ielādēts no cdn.jsdelivr.net; bez tīkla norādi lokālu failu: AXE_PATH=.../axe.min.js
Izejas kods 1, ja ir kritiskas/nopietnas axe kļūdas, horizontāla ritināšana vai neizdodas tastatūras ceļš.
Rezultātus pārnes uz templates/accessibility.html (F8).
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AXE_URL = "https://cdn.jsdelivr.net/npm/axe-core@4.10.3/axe.min.js"
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
PAGES = {  # lietotāja ID sēklas datos → ekrāni
    1: ["/", "/organizacijas", "/organizacijas?q=Ezermalas", "/organizacijas/jauna", "/organizacijas/1",
        "/organizacijas/1/kontakti/jauns", "/kontakti/1/labot", "/organizacijas/1/mijiedarbibas/jauna",
        "/pieprasijumi", "/pieprasijumi/1/atbilde", "/organizacijas/1/pieprasijumi/jauns", "/uzdevumi"],
    4: ["/parskats"],
    5: ["/administresana", "/administresana?beigusies=1"],
    None: ["/sakums", "/pieklustamiba"],
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    tmp = tempfile.mkdtemp()
    env = {**os.environ, "CRM_DB": os.path.join(tmp, "a11y.db"), "CRM_AI_OFFLINE": "1"}
    server = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "app", "run", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        return run_checks(base)
    finally:
        server.terminate()


def run_checks(base: str) -> int:
    axe_path = os.environ.get("AXE_PATH")
    violations, incomplete, reflow, failures = [], set(), {}, []

    def axe(page, label):
        if axe_path:
            page.add_script_tag(path=axe_path)
        else:
            page.add_script_tag(url=AXE_URL)
        result = page.evaluate("tags => axe.run(document, {runOnly: {type: 'tag', values: tags}})", TAGS)
        for v in result["violations"]:
            violations.append((label, v["impact"], v["id"], len(v["nodes"]), v["nodes"][0]["target"]))
        for i in result["incomplete"]:
            incomplete.add((i["id"], label.split(" ", 1)[1]))

    def login(page, uid):
        page.goto(base + "/sakums")
        page.check(f"#u{uid}")
        page.click("button[type=submit]")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("light", "dark"):
            for uid, urls in PAGES.items():
                ctx = browser.new_context(color_scheme=scheme)
                page = ctx.new_page()
                if uid:
                    login(page, uid)
                for url in urls:
                    page.goto(base + url)
                    axe(page, f"{scheme} {url}")
                if uid == 1:  # kļūdu un MI melnraksta stāvokļi
                    page.goto(base + "/organizacijas/jauna")
                    page.click("text=Saglabāt")
                    axe(page, f"{scheme} org-forma-ar-kludam")
                    page.goto(base + "/organizacijas/1/mijiedarbibas/jauna")
                    page.click("summary")
                    page.fill("#f-notes", "Zvanīja klients. Jautāja par semināru. Vienojāmies nosūtīt programmu.")
                    page.click("text=Ģenerēt ar MI")
                    axe(page, f"{scheme} mi-1-melnraksts")
                ctx.close()

        # WCAG 1.4.10 / 1.4.4: 640 px ≈ 200 % mērogs 1280 px logā, 320 px ≈ 400 %
        for width in (640, 320):
            for uid, urls in PAGES.items():
                ctx = browser.new_context(viewport={"width": width, "height": 900})
                page = ctx.new_page()
                if uid:
                    login(page, uid)
                for url in urls:
                    page.goto(base + url)
                    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    if overflow > 0:
                        reflow[f"{width}px {url}"] = overflow
                ctx.close()

        # Tastatūra: izlaišanas saite un galvenais ceļš «Sākums → uzdevums izpildīts» tikai ar Tab/Enter
        ctx = browser.new_context()
        page = ctx.new_page()
        login(page, 1)
        page.goto(base + "/")
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.textContent.trim()") != "Pāriet uz saturu":
            failures.append("pirmais Tab nav izlaišanas saite")
        page.keyboard.press("Enter")
        if page.evaluate("document.activeElement.id") != "saturs":
            failures.append("izlaišanas saite nepārvieto fokusu")
        tabs = 0
        for tabs in range(1, 40):
            page.keyboard.press("Tab")
            if page.evaluate("document.activeElement.textContent.includes('Izpildīts')"):
                break
        else:
            failures.append("poga «Izpildīts» nav sasniedzama ar tastatūru")
        if page.evaluate("getComputedStyle(document.activeElement).outlineStyle") == "none":
            failures.append("fokuss nav redzams")
        page.keyboard.press("Enter")
        page.wait_for_load_state()
        if "izpildīts" not in (page.locator(".flash").first.text_content() or ""):
            failures.append("uzdevumu neizdevās atzīmēt ar tastatūru")
        browser.close()

    pages_checked = sum(len(u) for u in PAGES.values()) + 2
    print(f"axe-core ({len(TAGS)} WCAG tagi): {pages_checked} ekrāni × 2 krāsu režīmi")
    for v in violations:
        print("  PĀRKĀPUMS", *v)
    print(f"  pārkāpumi: {len(violations)}")
    for rule, label in sorted(incomplete):
        print(f"  jāpārbauda manuāli: {rule} — {label}")
    print(f"Pārplūde 640/320 px: {reflow or 'nav'}")
    print(f"Tastatūra: {'OK' if not failures else failures} (poga «Izpildīts» pēc {tabs} Tab)")
    serious = [v for v in violations if v[1] in ("critical", "serious")]
    return 1 if serious or reflow or failures else 0


if __name__ == "__main__":
    sys.exit(main())
