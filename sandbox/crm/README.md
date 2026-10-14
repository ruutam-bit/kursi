# Sadarbības CRM (mācību demo)

Flask, servera pusē renderēts HTML (viens process), Jinja2, SQLite. Prasības, ekrānu karte un Definition of Done: [PRASIBAS.md](PRASIBAS.md). Visi dati ir sintētiski.

```bash
cd sandbox/crm
pip install -r requirements.txt
flask --app app run --debug          # http://127.0.0.1:5000 → izvēlies lomu
pytest -q tests/test_crm.py

# piekļūstamība pārlūkā (axe-core + Playwright)
pip install playwright && python -m playwright install chromium
python tests/a11y_check.py
```

## Arhitektūra

| Slānis | Faili |
|---|---|
| Saskarne | `templates/` — Jinja2 šabloni; `base.html`: izlaišanas saite, orientieri, fokuss; `macros.html`: lauki ar `label` un kļūdu tekstu |
| Lietojuma loģika | `app.py` — maršruti, validācija ar kļūdu ziņām, statusi un termiņi (kavēts = aprēķins), meklēšana, «šodienas» uzdevumi, loma sesijā, piekļuves žurnāls, POST → redirect → GET |
| Dati | `db.py` → `data.db`: `organizacijas`, `kontakti`, `mijiedarbibas`, `pieprasijumi`, `uzdevumi`, `piekluves_zurnals`, `mi_zurnals`, `lietotaji` |
| MI komponents | `ai.py` — `kopsavilkums()` (MI-1), `atbildes_projekts()` (COULD); Claude vai atslēgvārdu imitācija ar vienādu līgumu |
| Testi | `tests/test_crm.py` (pytest), `tests/a11y_check.py` (axe-core + Playwright) |

## Iestatījumi

- `data.db` un sākumdati (10 organizācijas, 20 kontakti, 30 mijiedarbības) tiek izveidoti pirmajā palaišanā. Lai sāktu no jauna, izdzēs `data.db`. Cits ceļš: `CRM_DB`.
- MI izmanto Claude (`claude-opus-5-5`), ja ir Anthropic akreditācijas dati (piem., `ANTHROPIC_API_KEY`). Bez tiem vai ar `CRM_AI_OFFLINE=1` darbojas atslēgvārdu imitācija; marķējumā redzams modeļa nosaukums.
- `CRM_SECRET_KEY` — sesijas atslēga; ja nav iestatīta, tiek ģenerēta katrā palaišanā.
- `AXE_PATH` — lokāls `axe.min.js`, ja `a11y_check.py` nav piekļuves cdn.jsdelivr.net.
