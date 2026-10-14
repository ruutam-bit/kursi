# MI-COULD · E-pasta atbildes projekts

| | |
|---|---|
| **Grupa** | MI komponents (COULD — vēlama, ne obligāta) |
| **Statuss** | ✅ Īstenots · testi 2/2 izturēti (tikai imitācijas režīmā) |
| **MI akta riska klase** | **Minimāls** — iekšējs teksts; cilvēks pārbauda un nosūta; marķēts |
| **Lomas** | Darbinieks, vadītājs (savu organizāciju pieprasījumiem) |
| **Ekrāni** | «Atbildes projekts» — no pieprasījumu saraksta |
| **Kods** | `ai.py`: `atbildes_projekts`; `app.py`: `request_reply`; `templates/request_reply.html` |
| **Saistītās** | [F4](F4.md), [MI-1](MI-1.md) |

## Mērķis

Palīdzēt ātrāk atbildēt uz organizācijas pieprasījumu, saglabājot cilvēka kontroli pār to, kas tiek nosūtīts.

## Funkcijas līgums

```
atbildes_projekts(temats: str, teksts: str) -> AtbildesProjekts(text: str, model: str)
```

## Maršruts

`GET, POST /pieprasijumi/<id>/atbilde` — saite «Atbildes projekts» katrā pieprasījumu saraksta rindā.

## Detalizētās prasības

- MC.1 Ekrānā: pieprasījuma tēma, organizācija, termiņš, statuss; paziņojums, ka MI sagatavo **projektu**, sistēma e-pastu **nesūta**, e-pasti un tālruņi tiek aizstāti.
- MC.2 Lauks «Iekšējās piezīmes — ko atbildēt» (obligāts) un poga «Ģenerēt projektu ar MI». Tukšām piezīmēm — 422 un «Ieraksti iekšējās piezīmes — ko atbildēt.».
- MC.3 Rezultāts — sadaļā «Projekts»: marķējums «Ģenerēts ar MI (<modelis>) — pārbaudi un labo pirms nosūtīšanas» un rediģējams teksta lauks «E-pasta teksts (vari labot un kopēt)».
- MC.4 Projekts **netiek saglabāts** datubāzē.
- MC.5 Poga «Atzīmēt, ka nosūtīju no sava e-pasta» ieraksta MI žurnālā rezultātu «cilvēks nosūtīja» un atgriež uz pieprasījumu sarakstu ar paziņojumu «Atzīmēts, ka atbildi nosūtīji. Ja jautājums atrisināts, maini pieprasījuma statusu.».
- MC.6 Pieprasījuma statuss automātiski **netiek** mainīts — to dara cilvēks ([F4](F4.md)).
- MC.7 Datu minimizācija: tā pati `redact()` kā [MI-1](MI-1.md); pieprasījuma tēma tiek nodota birkā `<pieprasijums>`, piezīmes — `<piezimes>`, abas kā dati, ne instrukcijas.
- MC.8 Claude: tas pats modelis un iestatījumi kā MI-1; JSON shēma `{body}`; uzvedne — pieklājīga, lietišķa atbilde latviski bez uzrunas vārdā un paraksta, trūkstošā informācija kvadrātiekavās.
- MC.9 Imitācija: veidne «Labdien! Paldies par Jūsu pieprasījumu «<tēma>». <piezīmes>. Ja rodas papildu jautājumi, lūdzu, sazinieties ar mums.».
- MC.10 Svešas organizācijas pieprasījumam — **404**.

### MI žurnāls

| Notikums | Komponents | Rezultāts |
|---|---|---|
| Ģenerēšana | E-pasta atbildes projekts | ģenerēts melnraksts |
| «Nosūtīju» | E-pasta atbildes projekts | cilvēks nosūtīja |

## Testi

`test_reply_draft_marked_and_human_sends`, `test_reply_for_foreign_request_hidden`.

## Ierobežojumi

- Claude implementācija nav testēta (nav API atslēgas).
- Sistēma nepārbauda, vai e-pasts tiešām nosūtīts — «nosūtīju» ir darbinieka apliecinājums.
- Kopēšanas pogas nav — teksts jāatlasa un jākopē manuāli.
