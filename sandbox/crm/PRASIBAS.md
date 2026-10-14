# CRM · Prasību saraksts

> Avoti: uzdevuma attēls «Situācija + prasību tabula» un «Konceptuālā arhitektūra: CRM mazai iestādei» (M01). Visi dati lietotnē ir sintētiski.

## Situācija

Iestāde ar ~25 darbiniekiem sadarbojas ar uzņēmumiem, NVO un pašvaldībām — konsultācijas, semināri, pieprasījumi. Šodien viss ir Excel tabulās un personīgajos e-pastos: neviens nezina, kas ar ko pēdējo reizi runāja. Vajadzīga viena klientu attiecību sistēma (CRM).

**Caurviju jautājums — personas dati.** Atšķirībā no «Iesniegumiem» CRM glabā kontaktpersonu — fizisku personu — datus. Tāpēc VDAR prasības (N2) ir prasību sarakstā, nevis pielikumā, un no tām izriet divas arhitektūras atšķirības: **trešā loma — administrators** (lomas, dzēšana, žurnāls) un **piekļuves žurnāls** (kas, ko, kad skatīja vai mainīja).

Apzīmējumi: **F** — funkcionālās, **MI** — MI komponenti, **N** — nefunkcionālās prasības.
Statuss: ✅ īstenots · 📝 tikai klasificēts (nebūvē).

## Funkcionālās prasības

| ID | Prasība | Pieņemšanas kritēriji | Ekrāns | Statuss |
|---|---|---|---|---|
| F1 | Organizācijas: izveidot, rediģēt, meklēt | Lauki: nosaukums, reģ. nr. (11 cipari), veids (uzņēmums / NVO / pašvaldība), atbildīgais darbinieks. Formā katram laukam ir `label`; kļūda ir teksts pie lauka (`aria-describedby`, `aria-invalid`) un kļūdu kopsavilkumā, ne tikai krāsa. Negatīvi: tukšs nosaukums, reģ. nr. ne 11 cipari, dublēts reģ. nr., nezināms veids → forma ar kļūdu tekstu (422). Darbinieks nevar pārcelt organizāciju citam. | Organizācijas: saraksts; kartīte | ✅ |
| F2 | Kontaktpersonas pie organizācijas | Tikai vajadzīgie lauki (VDAR datu minimizācija): vārds, amats, e-pasts, tālrunis, saziņas pamats, pamata datums. Nav personas koda, adreses, brīvu piezīmju. Jābūt vismaz e-pastam vai tālrunim. Forma gan jaunam kontaktam, gan labošanai; glabāšanas termiņu pārrēķina. | Kontakta forma | ✅ |
| F3 | Mijiedarbību žurnāls | Veids: zvans / e-pasts / sanāksme; datums, dalībnieki (tikai šīs organizācijas kontakti), kopsavilkums, nākamais solis. Organizācijas kartītē hronoloģiski (jaunākā augšā). | Kartīte; Mijiedarbība + MI-1 | ✅ |
| F4 | Pieprasījumi no organizācijām | Statuss Jauns → Darbā → Atbildēts (tikai uz priekšu, citādi 409). Termiņš. **Kavēts ir aprēķins** (termiņš pagājis un nav «Atbildēts»), attēlots ar tekstu «Kavēts» un ikonu, ne tikai krāsu. | Pieprasījumi, statusi | ✅ |
| F5 | Uzdevumi un atgādinājumi | «Mani uzdevumi šodien» (termiņš ≤ šodien, nav izpildīts). Atzīmēt kā izpildītu (tikai savus). Uzdevums obligāti saistīts ar organizāciju vai pieprasījumu. | Mani uzdevumi; Sākums | ✅ |
| F6 | Meklēšana | Viens lauks organizāciju saraksta ekrānā pāri organizācijām, kontaktiem, pieprasījumiem. Rezultāti tabulās ar `caption` un `th scope`. Darbinieks redz tikai savu organizāciju rezultātus. | Organizācijas: saraksts | ✅ |
| F7 | Pārskats vadītājam | Aktivitāte pa darbiniekiem (mijiedarbības 30 dienās), kavētie pieprasījumi, aktīvākās organizācijas. Diagramma + tie paši dati tabulā. Tikai lomai «vadītājs» (citiem 403). | Pārskats | ✅ |
| F8 | Piekļūstamības paziņojums | Lapa `/pieklustamiba` ar reāliem testa atradumiem; saite kājenē katrā lapā. | Paziņojums | ✅ |
| F9 | Kopsavilkuma ekrāns | Parādās uzreiz pēc lomas izvēles. Kopsavilkums lietotāja līmenī: manas organizācijas, atvērtie un kavētie pieprasījumi, šodienas uzdevumi, pēdējās mijiedarbības. | Sākums | ✅ |

## MI komponenti (`ai.py`)

Abām implementācijām — Claude (GPAI API) un atslēgvārdu imitācijai bez tīkla — ir vienāds funkciju līgums: `kopsavilkums(teksts) → kopsavilkums, solis` un `atbildes_projekts(temats, teksts) → teksts`. MI akta riska klase noteikta **pirms** izstrādes.

| ID | Prasība | Pieņemšanas kritēriji | Riska klase | Statuss |
|---|---|---|---|---|
| MI-1 | Mijiedarbības kopsavilkums un nākamais solis | No brīva teksta → 3 teikumi + nākamā soļa ieteikums. **Melnraksts** ar marķējumu «Ģenerēts ar MI» (un modeļa nosaukumu); darbinieks rediģē un apstiprina — bez apstiprināšanas nekas netiek saglabāts. MI žurnālā: ģenerēts / apstiprināts bez izmaiņām / ar labojumiem. E-pasti un tālruņi pirms nosūtīšanas modelim tiek aizstāti. | **Minimāls** — iekšējs palīgrīks, cilvēks apstiprina, lēmumus par personām nepieņem | ✅ |
| MI-COULD | E-pasta atbildes projekts uz pieprasījumu | No darbinieka iekšējām piezīmēm → atbildes teksts. Marķēts «Ģenerēts ar MI». Sistēma e-pastu **nesūta**: cilvēks pārbauda, nokopē un nosūta pats, tad atzīmē «nosūtīju» (MI žurnālā). | **Minimāls** — cilvēks nosūta; pārredzamības labā prakse: marķējums | ✅ |
| MI-2 | Organizāciju prioritizācija «pēc sadarbības potenciāla» | **TIKAI klasificēt**, nebūvēt. Skat. zemāk. | **KLASIFICĒ** — iespējams augsts | 📝 |

### MI-2 klasifikācija (ES MI akts, Regula 2024/1689)

Klasifikācija atkarīga no tā, **kam rezultāts tiek izmantots** — tāpēc tā paliek atklāta («KLASIFICĒ»), līdz pasūtītājs nosaka lietojumu.

| Lietojums | Riska klase | Pamatojums |
|---|---|---|
| Prioritizācija ietekmē, **kura organizācija saņem pakalpojumu** (konsultāciju, semināra vietu, atbalstu) | **Iespējams augsts** (III pielikums, 5. p. — piekļuve publiskiem pakalpojumiem un pabalstiem) | Valsts iestāde ar MI nosaka, kam sniegt publisku pakalpojumu; skar arī pašvaldības un NVO un caur tām — fiziskas personas. |
| Rezultāts tiek izmantots **darbinieku darba vērtēšanai** vai uzdevumu sadalei | **Augsts** (III pielikums, 4. p. — nodarbinātība) | «Potenciāls» darbinieka portfelī kļūst par darba snieguma rādītāju. |
| Tikai **darbinieka paša darba kārtība** (kuram piezvanīt vispirms), cilvēks izlemj | **Minimāls** | Nav lēmuma par pakalpojuma pieejamību; marķēt kā MI. |

- **Kas tiek vērtēts:** formāli organizācijas, bet ievaddati ir mijiedarbības ar kontaktpersonām (fiziskām personām) → VDAR profilēšana (4. p. 4. punkts): tiesiskais pamats, informēšana (13./14. p.), iebildumu tiesības (21. p.), automatizēti lēmumi (22. p.).
- **Sekas organizācijai:** zems vērtējums → mazāk uzmanības; valsts iestādei — vienlīdzīgas attieksmes risks pret pašvaldībām/NVO.
- **Lēmums:** **nebūvēt šajā versijā.** Pirms lēmuma «būvēt»: pasūtītājs nosaka lietojumu (tabulā), DPIA, kritēriji bez fizisko personu datiem. Alternatīva bez MI: F7 «aktīvākās organizācijas» un kavētie pieprasījumi jau dod caurskatāmu prioritizāciju.

## Nefunkcionālās prasības (caurviju — visos slāņos)

| ID | Prasība | Pieņemšanas kritēriji | Kā īstenots | Statuss |
|---|---|---|---|---|
| N1 | Piekļūstamība | EN 301 549 / WCAG 2.2 AA: axe-core bez critical/serious; tastatūra un 200 % mērogs galvenajā ceļā; 320 px. | `base.html`: `lang="lv"`, izlaišanas saite, orientieri, redzams fokuss. Formās `label`, kļūdas tekstā. Tabulās `caption` + `th scope`. HTML bez JS ietvariem. Pārbaudes: `tests/test_crm.py` (statiskās), `tests/a11y_check.py` (axe-core + Playwright). | ✅ (NVDA — manuāli, skat. DoD) |
| N2 | Personas dati (VDAR) | Datu minimizācija; glabāšanas termiņš kontaktam; piekļuves žurnāls (kas, ko, kad skatīja vai mainīja); dzēšana pēc pieprasījuma. | F2 minimālie lauki. `retain_until` = pamata datums + 3 gadi. `piekluves_zurnals`: katra organizācijas kartītes (ar kontaktiem) atvēršana, kontakta izveide/labošana (tikai lauku nosaukumi), lomu maiņa, dzēšana. Dzēš **administrators**; žurnālā paliek tikai ID un fakts. | ✅ |
| N3 | Lomas | **Darbinieks** — savas organizācijas, kontakti, žurnāls, uzdevumi. **Vadītājs** — visas organizācijas + pārskats. **Administrators** — lomas, dzēšana, piekļuves un MI žurnāls (bez piekļuves CRM darba ekrāniem). Lomas izvēle sākumlapā (bez parolēm, mācību režīms). | Loma sesijā; `require(...)` serverī katrā maršrutā (svešs ieraksts → 404, sveša loma → 403). Nevar noņemt pēdējo administratoru. | ✅ |
| N4 | Tehnoloģijas un laiks | Flask + Jinja2 + SQLite; Codespace + Claude Code; 1,5 h; sākumdati 10 / 20 / 30. | `db.py` sēklas dati (sintētiski), `data.db`. | ✅ |

## Ekrānu karte (arhitektūras saskarnes slānis)

| Grupa | Ekrāns | Prasības | Maršruts | Lomas |
|---|---|---|---|---|
| Organizācijas | Saraksts, meklēšana | F1, F6 | `/organizacijas` | D, V |
| | Kartīte: kontakti, žurnāls | F1, F2, F3, N2 | `/organizacijas/<id>` | D, V |
| | Kontakta forma | F2, N2 | `/organizacijas/<id>/kontakti/jauns`, `/kontakti/<id>/labot` | D, V |
| Darbs | Mijiedarbība + MI-1 | F3, MI-1 | `/organizacijas/<id>/mijiedarbibas/jauna` | D, V |
| | Pieprasījumi, statusi (+ atbildes projekts) | F4, MI-COULD | `/pieprasijumi`, `/pieprasijumi/<id>/atbilde` | D, V |
| | Mani uzdevumi | F5 | `/uzdevumi` | D, V |
| Vadība | Pārskats: tabula, diagramma | F7 | `/parskats` | V |
| Visi | Sākums / loma | F9, N3 | `/sakums`, `/` | visi |
| | Paziņojums | F8 | `/pieklustamiba` | visi |
| Administrēšana | Lomas, dzēšana, žurnāli | N2, N3 | `/administresana` | A |

Palīgformas: organizācijas forma (F1) un pieprasījuma reģistrācija (F4) — tiek atvērtas no kartītes.

## Definition of Done

Prasība ir «gatava», ja:

1. Pieņemšanas kritēriji (arī negatīvie) ir pārklāti ar testiem `tests/test_crm.py`, un `make test` ir zaļš.
2. `python tests/a11y_check.py` beidzas ar kodu 0 (axe-core bez critical/serious, nav pārplūdes 640/320 px, tastatūras ceļš strādā).
3. Ja ekrāns rāda vai maina kontaktpersonu datus — darbība ir piekļuves žurnālā; ja ir MI — marķējums, cilvēka apstiprinājums un ieraksts MI žurnālā.
4. Manuālie testi (zemāk) veikti jaunajam vai mainītajam ekrānam.
5. Diff pārskatīts: nav piekļuves datu, nav reālu personas datu; viens commit uz prasību, ziņojums sākas ar prasības/pieteikuma ID.

### Manuālie testi

| Tests | Kā | Pēdējais rezultāts |
|---|---|---|
| Tastatūra | Viss galvenais ceļš (loma → organizācija → mijiedarbība ar MI → saglabāt) tikai ar Tab / Shift+Tab / Enter / Space; fokuss vienmēr redzams | Automatizēti daļēji (`a11y_check.py`); pilns manuāls ceļš — jāveic |
| 200 % mērogs | Pārlūka tālummaiņa 200 % un 400 %, nav horizontālas ritināšanas, nekas nepārklājas | Automatizēti (640/320 px) — OK |
| NVDA | Firefox + NVDA: orientieri, virsraksti, formu kļūdas tiek nolasītas, tabulu galvenes, «Ģenerēts ar MI» paziņojums | Nav veikts |

## Ārpus apjoma

- Īsta autentifikācija (paroles, SSO) — mācību režīms N3.
- E-pasta sūtīšana no sistēmas, kalendārs, failu pielikumi.
- MI-2 prioritizācija (tikai klasificēta).
- Produkcijas izvietošana.

## Zināmie ierobežojumi

- Dzēšot kontaktpersonu, mijiedarbību kopsavilkumi paliek organizācijas vēsturē. Ja brīvajā tekstā minēts personas vārds, tas netiek automātiski izņemts — mijiedarbību rediģēšana šajā versijā nav īstenota.
- Piekļuves žurnāls un MI žurnāls netiek automātiski tīrīti; to glabāšanas termiņš jānosaka iestādes datu aizsardzības speciālistam.
- Piekļuves žurnāls fiksē organizācijas kartītes atvēršanu (kurā redzami tās kontakti), nevis katru kontaktu atsevišķi; «kurš redzēja kontaktu X» = kartītes skatījumi, kamēr kontakts pastāvēja.
