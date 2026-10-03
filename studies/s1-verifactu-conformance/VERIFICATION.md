# VERIFICATION — review of findings and of the classification

> **Who reviewed.** Every check below was performed one by one by the LLM-based
> study agent (reading files, normative texts and test code, and running the
> independent hash implementation).

Study S1, 2026-10-02. Files are named by anonymised IDs; the mapping to real paths is
in `private/`. Normative texts were downloaded to `data/raw/norma/` (BOE XML, AEAT
PDFs converted with `pdftotext -layout`) and are quoted literally below.

## 1. Every ERROR on class-(a) files was checked (22 of 22)

The protocol asked for at least 10. The class-(a) corpus is small enough to check all
22 ERROR findings (10 files, 6 repositories). Of the 9 RRSIF001 files, 7 (5
repositories) are true hash mismatches; the other 2 (1 repository, R02) carry no hash
in the official field.

| # | Rule | Files (repos) | Check performed | Verdict |
|---|---|---|---|---|
| 1–7 | RRSIF001 «La huella declarada no coincide» | 7 (5) | Hash recomputed with an **independent implementation** (`scripts/05_sample.py`, no code shared with verifactu-lint) over the eight fields of Orden HAC/1177/2024 art. 13.1.a (alta) or the five of
13.1.b (anulación). In 7/7 the independent hash ≠ declared hash. Where amounts carry trailing zeros, verifactu-lint's displayed «Calculada» is a different admissible numeric variant; neither variant matches. | **7 TP** |
| 8–9 | RRSIF001 «no informa el campo Huella» | 2 (1) | The record carries `<Huella><Hash>…</Hash></Huella>` — a nested structure that does not exist in `SuministroInformacion.xsd` (`<element name="Huella" type="sf:TextMax64Type"/>`). | **2 TP**, misleading message (see I-2) |
| 10–12 | RRSIF002 «La huella está en minúsculas» | 3 (1) | Declared hashes are lowercase hex. AEAT hash specification: «En sistema hexadecimal. En mayúsculas.» | **3 TP** |
| 13–16 | RRSIF011 IdSistemaInformatico / NumeroInstalacion | 2 (1) | `SistemaInformatico` contains only `<Nombre>` and `<Version>`. | **4 TP** |
| 17–18 | RRSIF030 «no informa TipoFactura» | 2 (1) | `TipoFactura` exists, but nested under an invented `<Factura>` element, not as a child of `RegistroAlta`. | **2 TP** against the schema, misleading message (I-2) |
| 19–20 | RRSIF040 «no tiene desglose» | 2 (1) | Same files: `<Factura><Desglose><DetalleIVA>…` instead of `Desglose/DetalleDesglose`. | **2 TP** against the schema, misleading message (I-2) |
| 21 | RRSIF043 «La cuota de la línea no sale de su base y su tipo» | 1 (1) | Base 2500.00, TipoImpositivo 15.00, CuotaRepercutida 220.00: 2500 × 15 % = 375.00, |375 − 220| = 155 > 10 € tolerance. | **TP** |
| 22 | RRSIF049 «Una factura F1 sin destinatario» | 1 (1) | `TipoFactura` F1, no `Destinatarios`. AEAT *Validaciones y errores* v1.2.2, ap. 13: «Si TipoFactura es "F1", "F3", "R1", "R2", "R3" o "R4", la agrupación Destinatarios tiene que estar cumplimentada, con al menos un destinatario.» | **TP** |

**Instrument false-positive rate on ERROR: 0/22** (Wilson 95% upper bound 14.9%).
The 22 findings are not independent (10 come from two files of one generator). Over
the 20 distinct file–rule pairs the upper bound is 16.1%; over the 12 distinct
repository–rule situations, 24.3%. (An earlier draft said «closer to 13»; the
computed count is 12.) The independent hash implementation was written by the same
team: it rules out coding bugs, not a shared misreading of the specification.

Supporting literal texts:

- Orden HAC/1177/2024, art. 13.1.a: «Para el registro de facturación de alta: 1.º NIF
  del emisor. 2.º Numero de factura y serie. 3.º Fecha de expedición de la factura.
  4.º Tipo de factura. 5.º Cuota total. 6.º Importe total. 7.º Huella del registro de
  facturación anterior. 8.º Fecha, hora y huso horario de generación del registro.»
- RD 1007/2023, art. 12: «Los sistemas informáticos indicados en el artículo 7 de este
  Reglamento deberán añadir una huella o «hash» a los registros de facturación de alta y
  de anulación […] según las especificaciones que se determinen.»

## 2. AVISO findings (4) and what they mean

| Rule | Verdict |
|---|---|
| RRSIF005 «No se informa TipoHuella» (2 files, 1 repo) | TP: `TipoHuella` is a mandatory element of `RegistroAlta` in the XSD and is absent. |
| RRSIF042 «ImporteTotal no cuadra» (1) | TP as AVISO: 2500 + 220 = 2720 vs declared 2715; the 5 € gap is inside the AEAT ±10 € margin, so warning rather than error is the correct severity. |
| RRSIF027 «Fin como NO VERI\*FACTU sin inicio previo» (1) | **Out of scope / severity issue.** The file is a one-event fixture (the shutdown event alone, one of eleven one-event fixtures in the same repository). The start may live in another file; this should be INCOMPLETO, not AVISO (I-5). |

## 3. Classification review

| Sample | Result | Action |
|---|---|---|
| All 4 occurrences sent to (b) by the first heuristics | **4/4 wrong.** Three were *golden* files used to assert that generated XML equals the fixture (the `toThrow` or `invalid` that triggered the ±12-line window belonged to a neighbouring test or to an in-memory mutation of the fixture); one was `…-rejection-correction.xml`, a valid `RechazoPrevio` resubmission. | Window narrowed to the enclosing test case; positive signals (`golden`, `assertValid`…) override; `reject/rechaz` removed from path tokens. After the fix, 0 occurrences in (b). |
| All 46 final (a) occurrences | Paths of all 46 read one by one; contents of every file with an ERROR or AVISO, and of the test code around every fixture referenced by tests (10), inspected. No deliberately invalid fixture found. 11 are one-event fixtures of a single repository; 3 are output files of one generator; the rest are examples, docs or golden fixtures. | none |
| All 91 (d) «valores de relleno» | The matching value was tabulated for every occurrence (first match: `NIF`=`AAAA` 46, `Huella`=`0123456789ABCDEF…` 18, `Huella`=64×`A` 12, `Huella`=`HuellaRegistroAnterior` 10, the rest `XXXX`/`huella`/`AAA`). The `AAAA`/`NNNN`/`Huella` values are exactly those of the examples in the AEAT *Descripción del servicio web*, ap. 9 (e.g. «`<sum1:Huella>HuellaRegistroAnterior</sum1:Huella>`»). | none |
| (d) «marcador de plantilla» (32), (e) (73), (c) (12) | **Not reviewed.** Errors there could move files in either direction; their effect on the rate is unknown. | pending |
| Older variant of the AEAT signature example `ejemploRegistro.xml` (3 contents, 2 repos, 6 copies) | Its `RegistroAnterior/Huella` is the literal string `huella` (lowercase), which the first placeholder rule missed; its declared hash does not recompute. Moved to (d). The newer variant (C9AF…/FF95… hashes) is in (a) and passes. | rule made case-insensitive |

One class-(a) file could not be read: it is not well-formed XML (a Pascal string
literal `'#$D#$A` is appended after the closing envelope). It is reported in the
funnel and excluded from the denominators.
