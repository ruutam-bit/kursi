# Prasību kopsavilkums · Sadarbības CRM

Testēšanas datums: 2026-10-14 · Zars: `crm-mvp` · Kods: [`sandbox/crm/`](../sandbox/crm/) · Pilnas prasības un pieņemšanas kritēriji: [`sandbox/crm/PRASIBAS.md`](../sandbox/crm/PRASIBAS.md)

**Kopā:** 16 prasības — 14 īstenotas, 1 īstenota daļēji (N1), 1 tikai klasificēta (MI-2). Testēšanas rezultāts: 12 izturētas, 3 izturētas ar piezīmi, 1 nav testējama. Automātiskie testi: **55/55 izturēti** (`pytest`), **0 pārkāpumu** pārlūka piekļūstamības pārbaudē (`a11y_check.py`).

Statusi: ✅ Īstenots · 🟡 Daļēji · 📝 Klasificēts (nebūvē)
Testēšanas rezultāti: ✅ Izturēts · ⚠️ Izturēts ar piezīmi · ⬜ Nav testēts

| ID | Prasība | Statuss | Testēšanas rezultāts | Testi |
|---|---|---|---|---|
| F1 | Organizācijas: izveidot, rediģēt, meklēt | ✅ Īstenots | ✅ Izturēts (7/7) | `test_create_org_and_search`, `test_org_validation_errors_as_text` ×4 (tukšs nosaukums, reģ. nr. ≠ 11 cipari, dublēts reģ. nr., nezināms veids), `test_employee_cannot_reassign_org`, `test_org_card_shows_contacts_and_logs_view` |
| F2 | Kontaktpersonas pie organizācijas | ✅ Īstenots | ✅ Izturēts (3/3) | `test_contact_requires_email_or_phone`, `test_contact_create_edit_retention_and_log`, `test_employee_cannot_edit_foreign_contact` |
| F3 | Mijiedarbību žurnāls | ✅ Īstenots | ✅ Izturēts (2/2) | `test_interactions_chronological`, `test_interaction_rejects_foreign_contact` |
| F4 | Pieprasījumi no organizācijām (statusi, termiņi, kavēti) | ✅ Īstenots | ✅ Izturēts (3/3) | `test_overdue_marked_with_text`, `test_request_status_only_forward`, `test_open_redirect_blocked` |
| F5 | Uzdevumi un atgādinājumi | ✅ Īstenots | ✅ Izturēts (2/2) | `test_task_create_requires_link_and_mark_done`, `test_cannot_complete_foreign_task` |
| F6 | Meklēšana pāri organizācijām, kontaktiem, pieprasījumiem | ✅ Īstenots | ✅ Izturēts (1/1) | `test_search_across_entities_respects_scope` |
| F7 | Pārskats vadītājam (diagramma + tabula) | ✅ Īstenots | ✅ Izturēts (2/2) | `test_manager_sees_all_and_overview`, `test_role_boundaries` (darbiniekam 403) |
| F8 | Piekļūstamības paziņojums | ✅ Īstenots | ✅ Izturēts | Saite kājenē pārbaudīta visos 15 `test_a11y_static_checks`; lapā ir reālie `a11y_check.py` atradumi |
| F9 | Kopsavilkuma ekrāns (sākums) | ✅ Īstenots | ✅ Izturēts (1/1) | `test_dashboard_after_login` |
| MI-1 | Mijiedarbības kopsavilkums un nākamais solis | ✅ Īstenots | ⚠️ Izturēts ar piezīmi (2/2) | `test_ai_summary_is_draft_until_confirmed`, `test_offline_summary_contract_three_sentences_and_redacts`. **Piezīme:** testēta tikai atslēgvārdu imitācija; Claude API izsaukums nav testēts (nav API atslēgas) |
| MI-COULD | E-pasta atbildes projekts | ✅ Īstenots | ⚠️ Izturēts ar piezīmi (2/2) | `test_reply_draft_marked_and_human_sends`, `test_reply_for_foreign_request_hidden`. **Piezīme:** tāpat kā MI-1 — tikai imitācijas režīms |
| MI-2 | Organizāciju prioritizācija | 📝 Klasificēts (nebūvē) | ⬜ Nav testējams | Riska klase «KLASIFICĒ»: augsts risks, ja ietekmē pakalpojuma saņemšanu (III pielikums); minimāls, ja tikai darba kārtība |
| N1 | Piekļūstamība (EN 301 549 / WCAG 2.2 AA) | 🟡 Daļēji | ⚠️ Automātiski izturēts; manuāli daļēji | `test_a11y_static_checks` 15/15; `a11y_check.py`: axe-core 0 pārkāpumu (19 ekrāni × gaišais/tumšais režīms), pārplūde 640/320 px — nav, tastatūras ceļš — OK. Atrastas un izlabotas 2 kļūdas (pārplūde 320 px, mērķa izmērs WCAG 2.5.8). **Nav veikts:** NVDA ekrāna lasītāja tests |
| N2 | Personas dati (VDAR) | ✅ Īstenots | ✅ Izturēts (5/5) | `test_contact_create_edit_retention_and_log` (glabāšanas termiņš, žurnāls), `test_org_card_shows_contacts_and_logs_view`, `test_employee_cannot_delete_contact`, `test_admin_deletes_contact_on_request`, `test_admin_sees_expired_contacts_and_access_log` |
| N3 | Lomas (darbinieks, vadītājs, administrators) | ✅ Īstenots | ✅ Izturēts (12/12) | `test_anonymous_redirected_to_role_choice`, `test_post_without_csrf_rejected`, `test_employee_sees_only_own_orgs`, `test_role_boundaries` ×7, `test_admin_lands_on_admin_screen`, `test_admin_changes_role_and_keeps_last_admin` |
| N4 | Tehnoloģijas un sākumdati | ✅ Īstenots | ✅ Izturēts (1/1) | `test_seed_counts` (10 organizācijas, 20 kontakti, 30 mijiedarbības) |

## Atklātie jautājumi

1. **MI-1 un MI-COULD:** pārbaudīt ar īstu Claude API atslēgu: 3 teikumu formāts, marķējums ar modeļa nosaukumu, e-pasta adreses un tālruņi aizstāti pirms nosūtīšanas.
2. **N1:** veikt manuālu testu ar NVDA un Firefox (orientieri, formu kļūdas, tabulu galvenes, MI paziņojums).
3. **MI-2:** pasūtītājam jānosaka lietojums, pirms var izlemt «būvēt vai nē».

## Kā atkārtot

```bash
make test                                   # visi pytest testi
cd sandbox/crm && python tests/a11y_check.py   # axe-core + Playwright (vajag playwright un chromium)
```
