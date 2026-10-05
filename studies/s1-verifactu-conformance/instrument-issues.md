# instrument-issues — verifactu-lint 0.4.0 as seen by study S1

No ERROR finding on the class-(a) corpus was a false positive (0/22, see
`VERIFICATION.md`). What the study did find is a set of **diagnostic-quality**,
**severity** and **coverage** issues. They were fixed in verifactu-lint 0.4.1 (2026-10-03); see its CHANGELOG.

## I-1 · Coverage gap: no check on the format of `FechaHoraHusoGenRegistro` (candidate)

Three files of one generator carry `FechaHoraHusoGenRegistro` values such as
`2025-11-29T14:03:11.312331`: microseconds and **no time-zone offset**. The field is
literally the «fecha, hora y **huso horario** de generación del registro» (Orden
HAC/1177/2024 art. 13.1.a.8.º) and every AEAT example writes it with an offset
(`2024-09-13T19:20:30+01:00`). verifactu-lint says nothing about it.

Status: **candidate, needs normative confirmation.** The XSD types the field as plain
`xs:dateTime` (`<element name="FechaHoraHusoGenRegistro" type="dateTime"/>`), which
admits values without offset; the explicit format requirement would have to come from
the AEAT record design or the validation document. A rule would probably be an AVISO.

Resolved: Orden HAC/1177/2024 art. 7.g) requires the time zone; verifactu-lint 0.4.1
reports its absence as ERROR (RRSIF053).

## I-2 · Diagnostics: a record that does not follow the schema gets a cascade of misleading messages

Two files of one repository use an invented structure (`<Factura><TipoFactura>`,
`<Huella><Hash>…</Hash></Huella>`, `<Desglose><DetalleIVA>`, ISO dates
`2026-05-01`). verifactu-lint reports «no informa el campo Huella», «no informa
TipoFactura», «no tiene desglose» — all *true* against the schema, but a developer
reading them will look for missing data that is actually present at the wrong path.

Suggestion: a structural pre-check (expected children of `RegistroAlta` /
`RegistroAnulacion`, or optional XSD validation when `lxml` is available) that emits
one ERROR «la estructura no corresponde al esquema» and names the unexpected
elements, before the semantic rules run.

## I-3 · Diagnostics: anulación with alta element names is reported only as a hash mismatch

One file writes a `RegistroAnulacion` whose `IDFactura` uses `IDEmisorFactura` /
`NumSerieFactura` / `FechaExpedicionFactura` instead of the `…Anulada` names required
by the schema. The parser reads the three fields as empty, the reference becomes
`#1 (sin NumSerieFactura)`, and the only finding is RRSIF001 (hash does not match).
Correct, but the root cause is invisible. A required-field rule for anulación records
(analogous to RRSIF030 for alta) would name it.

## I-4 · Coverage gap: date format of `FechaExpedicionFactura`

Same files as I-2: `FechaExpedicionFactura` = `2026-05-01`. The schema type is
`fecha` with pattern `dd-mm-yyyy`; AEAT rejects other formats. No rule fires. Low
priority (the XSD already catches it), but the README positions the tool as
complementary to the XSD, so the gap is worth stating.

## I-5 · Severity: RRSIF027 on a single-event file should be INCOMPLETO, not AVISO

A fixture containing only a «fin de funcionamiento como NO VERI\*FACTU» event gets
AVISO «Fin como NO VERI\*FACTU sin inicio previo». With one event in the file, the
start may simply live in an earlier file — the same situation in which RRSIF028
(resumen de eventos) already, and correctly, answers INCOMPLETO. The instrument's own
design rule («afirmar un incumplimiento que no existe es peor que callar uno que
sí») argues for INCOMPLETO whenever the file does not contain the start of the event
chain.

## I-6 · Usability: «Calculada» shows only one admissible variant

When amounts have trailing zeros (`21.40`), the hash finding prints the first
admissible variant (`21.4`). The independent recomputation of this study used the
literal value and got a different hash; both differ from the declared one, so the
verdict is right, but a user comparing against their own literal computation will see
a third value and may be confused. Printing the canonical string used for the
displayed hash would remove the ambiguity.

## Not an issue, for the record

- The two AEAT example families behave as expected: the newer signature example
  (`ejemploRegistro.xml`, hashes `C9AF…`/`FF95…`) passes all rules; the older variant,
  whose previous hash is the literal word `huella`, fails RRSIF001 — correctly.
- No crash, timeout or exception on 195 unique files; one file rejected as malformed
  XML with an accurate message.
