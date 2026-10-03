#!/usr/bin/env python3
"""Define the S7 fact set and queries, and verify every BOE reference literally.

Writes:
  data/facts.json          the 28 facts: current rule, old rule, BOE references, classification patterns
  data/facts.csv           flat table with the literal BOE quote found for each reference
  data/queries.csv         the natural-language queries (3-4 per fact)

Each BOE reference is checked against the downloaded text in data/raw/boe/ (scripts/fetch_boe.py):
the regex must match, and the matched passage (plus context) is stored as the quote.
A fact whose current-rule reference does not verify is reported and the script exits 1.
Stdlib only.
"""
import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOE = ROOT / "data/raw/boe"

def ref(boe_id, rx, con=False, note=""):
    return {"boe_id": boe_id, "consolidated": con, "rx": rx, "note": note}

# cur / old: regexes (case-insensitive) that signal the CURRENT rule or the SUPERSEDED rule in an answer.
# Thousands separators are normalised before matching (1.221 / 1 221 / 1221 all become 1221).
F = [
 dict(id="F01", area="labour", topic="Minimum wage (SMI) 2026",
      current="1.221 €/mes en 14 pagas (40,70 €/día), con efectos desde el 1-ene-2026", since="2026-02-19",
      old="1.184 €/mes (39,47 €/día) en 2025",
      boe=[ref("BOE-A-2026-3815", r"40,70 euros/día o 1 221 euros/mes")],
      boe_old=[ref("BOE-A-2025-2576", r"39,47 euros/día o 1184 euros/mes")],
      cur=[r"\b1221\s*(€|euros|eur)", r"\b40,70\b"], oldrx=[r"\b1184\s*(€|euros|eur)", r"\b39,47\b"],
      q=["cuál es el salario mínimo interprofesional", "cuánto es el SMI en 2026",
         "salario mínimo en España al mes", "SMI 14 pagas cuánto es"]),
 dict(id="F02", area="labour", topic="Birth leave length",
      current="19 semanas por progenitor (RDL 9/2025, en vigor 31-jul-2025)", since="2025-07-31",
      old="16 semanas",
      boe=[ref("BOE-A-2025-15741", r"ampliación del permiso de nacimiento a diecinueve semanas"),
           ref("BOE-A-2015-11430", r"progenitor distinto de la madre biológica durante diecinueve semanas", con=True)],
      boe_old=[],
      cur=[r"\b19 semanas", r"diecinueve semanas"], oldrx=[r"\b16 semanas", r"dieciséis semanas"],
      q=["cuántas semanas es la baja por paternidad", "permiso por nacimiento cuántas semanas",
         "baja de maternidad cuánto dura en España", "permiso de paternidad 2026"]),
 dict(id="F03", area="labour", topic="Birth leave, single-parent families",
      current="32 semanas en familias monoparentales (RDL 9/2025)", since="2025-07-31",
      old="26 semanas (criterio transitorio tras la STC 140/2024) o 16 semanas",
      boe=[ref("BOE-A-2015-11430", r"monoparentalidad, por existir una única persona progenitora, el periodo de suspensión será de treinta y dos semanas", con=True)],
      boe_old=[],
      cur=[r"\b32 semanas", r"treinta y dos semanas"], oldrx=[r"\b26 semanas", r"veintiséis semanas"],
      q=["permiso de maternidad familia monoparental cuántas semanas",
         "baja por nacimiento madre soltera semanas", "permiso por nacimiento familias monoparentales"]),
 dict(id="F04", area="labour", topic="Permanent disability no longer ends the job automatically",
      current="la incapacidad permanente total, absoluta o gran invalidez ya no extingue automáticamente el contrato: "
              "la persona trabajadora puede pedir ajustes razonables o cambio de puesto (Ley 2/2025)", since="2025-05-01",
      old="extinción automática del contrato (antiguo art. 49.1.e ET)",
      boe=[ref("BOE-A-2025-8567", r"condiciona la posibilidad de extinción del contrato por «declaración de gran incapacidad, incapacidad permanente absoluta o total de la persona trabajadora» a la voluntad de la persona trabajadora")],
      boe_old=[],
      cur=[r"ajustes razonables", r"ley 2/2025", r"ya no (se )?extingue", r"no (se )?extingue (de forma )?autom",
           r"(cambio|adaptaci[oó]n) (de|del) puesto"],
      oldrx=[r"(extingue|extinci[oó]n|fin|finaliza|termina)[^.]{0,50}autom[aá]tic", r"causa de (despido|extinci[oó]n)"],
      q=["la incapacidad permanente total extingue el contrato de trabajo",
         "me dan la incapacidad permanente total me pueden despedir",
         "incapacidad permanente total y contrato de trabajo", "qué pasa con mi trabajo si me dan la incapacidad permanente"]),
 dict(id="F05", area="labour", topic="Maximum working week (37.5h bill not passed)",
      current="40 horas semanales de promedio anual (art. 34.1 ET); la reducción a 37,5 h no se aprobó", since="(unchanged)",
      old="afirmar que la jornada de 37,5 h está aprobada o en vigor",
      boe=[ref("BOE-A-2015-11430", r"La duración máxima de la jornada ordinaria de trabajo será de cuarenta horas semanales", con=True)],
      boe_old=[],
      cur=[r"\b40 horas", r"cuarenta horas", r"no (se )?(ha )?(sido )?aprobad", r"rechaz", r"tumb", r"no sali[oó] adelante", r"no prosper", r"decay"],
      oldrx=[r"37[,.]5 horas"],
      q=["cuántas horas es la jornada laboral máxima en España",
         "jornada laboral 37,5 horas cuándo entra en vigor", "jornada máxima semanal 2026", "se ha aprobado la reducción de jornada a 37,5 horas"]),
 dict(id="F06", area="social-security", topic="Maximum contribution base 2026",
      current="5.101,20 €/mes desde el 1-ene-2026", since="2026-02-04",
      old="4.909,50 €/mes en 2025",
      boe=[ref("BOE-A-2026-7296", r"será, desde el 1 de enero de 2026, de 5\.101,20 euros mensuales")],
      boe_old=[ref("BOE-A-2025-3780", r"será, desde el 1 de enero de 2025, de 4\.909,50 euros mensuales")],
      cur=[r"\b5101,20\b"], oldrx=[r"\b4909,50\b"],
      q=["base máxima de cotización 2026", "cuál es la base máxima de cotización a la seguridad social",
         "tope máximo cotización seguridad social", "cuánto es la base máxima de cotización este año"]),
 dict(id="F07", area="social-security", topic="Intergenerational Equity Mechanism (MEI) 2026",
      current="0,90 % (0,75 % empresa + 0,15 % trabajador) en 2026", since="2026-01-01",
      old="0,80 % (0,67 % + 0,13 %) en 2025",
      boe=[ref("BOE-A-2026-7296", r"tipo del 0,90 por ciento sobre la base de cotización por contingencias comunes, del que el 0,75 por ciento será a cargo del empleador y el 0,15 por ciento")],
      boe_old=[ref("BOE-A-2025-3780", r"tipo del 0,80 por ciento sobre la base de cotización por contingencias comunes, del que el 0,67 por ciento será a cargo del empleador y el 0,13 por ciento")],
      cur=[r"\b0,90?\s*(%|por ciento)", r"\b0,75\s*(%|por ciento)", r"\b0,15\s*(%|por ciento)"],
      oldrx=[r"\b0,80?\s*(%|por ciento)", r"\b0,67\s*(%|por ciento)", r"\b0,13\s*(%|por ciento)"],
      q=["MEI 2026 porcentaje", "mecanismo de equidad intergeneracional cuánto es",
         "cotización MEI trabajador y empresa"]),
 dict(id="F08", area="social-security", topic="Solidarity contribution 2026",
      current="1,15 % / 1,25 % / … sobre la retribución que supera la base máxima (5.101,21 €) en 2026", since="2026-01-01",
      old="0,92 % / 1 % / 1,17 % en 2025",
      boe=[ref("BOE-A-2026-7296", r"La cuota de solidaridad será el resultado de aplicar un tipo del 1,15 por ciento a la parte de la retribución comprendida entre 5\.101,21 euros")],
      boe_old=[ref("BOE-A-2025-3780", r"La cuota de solidaridad será el resultado de aplicar un tipo del 0,92 por ciento")],
      cur=[r"\b1,15\s*(%|por ciento)", r"\b1,25\s*(%|por ciento)"], oldrx=[r"\b0,92\s*(%|por ciento)", r"\b1,17\s*(%|por ciento)"],
      q=["cuota de solidaridad 2026", "cuota de solidaridad seguridad social cuánto es",
         "cotización de solidaridad salarios altos porcentaje"]),
 dict(id="F09", area="social-security", topic="Pension uprating 2026",
      current="+2,7 % para las pensiones contributivas en 2026", since="2026-02-04",
      old="+2,8 % en 2025",
      boe=[ref("BOE-A-2026-2548", r"se revalorizarán en 2026 con carácter general el 2,7 por ciento")],
      boe_old=[ref("BOE-A-2025-1560", r"se revalorizarán en 2025 con carácter general el 2,8 por ciento")],
      cur=[r"\b2,7\s*(%|por ciento)"], oldrx=[r"\b2,8\s*(%|por ciento)"],
      q=["cuánto suben las pensiones este año", "subida de las pensiones 2026",
         "revalorización pensiones contributivas", "subida pensiones enero"]),
 dict(id="F10", area="social-security", topic="Non-contributory pension 2026",
      current="8.803,20 €/año (628,80 €/mes en 14 pagas)", since="2026-02-04",
      old="7.905,80 €/año (564,70 €/mes) en 2025",
      boe=[ref("BOE-A-2026-2548", r"tendrán un importe anual de 8\.803,20 euros")],
      boe_old=[ref("BOE-A-2025-1560", r"tendrán un importe anual de 7\.905,80 euros")],
      cur=[r"\b8803,20\b", r"\b628,80\b"], oldrx=[r"\b7905,80\b", r"\b564,70\b"],
      q=["cuánto es la pensión no contributiva", "pensión no contributiva 2026 cuantía",
         "pensión no contributiva jubilación al mes"]),
 dict(id="F11", area="social-security", topic="Maximum pension 2026",
      current="3.359,60 €/mes o 47.034,40 €/año", since="2026-02-04",
      old="3.267,60 €/mes o 45.746,40 €/año en 2025",
      boe=[ref("BOE-A-2026-2548", r"será de 3\.359,60 euros mensuales o 47\.034,40 euros anuales")],
      boe_old=[ref("BOE-A-2025-1560", r"3\.267,60 euros")],
      cur=[r"\b3359,60\b", r"\b47034,40\b"], oldrx=[r"\b3267,60\b", r"\b45746,40\b"],
      q=["pensión máxima 2026", "cuál es la pensión máxima de jubilación", "pensión máxima seguridad social al mes", "pensión máxima de jubilación este año"]),
 dict(id="F12", area="social-security", topic="Minimum retirement pension 2026",
      current="jubilación con 65 años: 17.592,40 €/año con cónyuge a cargo; 13.106,80 sin cónyuge; 12.441,80 con cónyuge no a cargo",
      since="2026-02-04", old="valores de 2025 (anexo del RDL 1/2025)",
      boe=[ref("BOE-A-2026-2548", r"Titular con sesenta y cinco años\. 17\.592,40 13\.106,80 12\.441,80")],
      boe_old=[ref("BOE-A-2025-1560", r"Titular con sesenta y cinco años\.? [\d.]+,\d\d [\d.]+,\d\d [\d.]+,\d\d")],
      cur=[r"\b17592,40\b", r"\b13106,80\b", r"\b12441,80\b", r"\b1256,60\b", r"\b936,20\b", r"\b888,70\b"], oldrx=[],  # old filled from BOE below
      q=["pensión mínima de jubilación con cónyuge a cargo", "pensión mínima jubilación 2026",
         "cuánto es la pensión mínima de jubilación"]),
 dict(id="F13", area="social-security", topic="Ordinary retirement age 2026",
      current="66 años y 10 meses (65 si se acreditan 38 años y 3 meses cotizados)", since="2026-01-01",
      old="66 años y 8 meses en 2025",
      boe=[ref("BOE-A-2015-11724", r"2026 38 años y 3 meses o más\. 65 años\. Menos de 38 años y 3 meses\. 66 años y 10 meses", con=True)],
      boe_old=[ref("BOE-A-2015-11724", r"2025 38 años y 3 meses o más\. 65 años\. Menos de 38 años y 3 meses\. 66 años y 8 meses", con=True)],
      cur=[r"66 años y 10 meses"], oldrx=[r"66 años y 8 meses", r"66 años y 6 meses"],
      q=["edad de jubilación 2026", "a qué edad me puedo jubilar", "edad ordinaria de jubilación en España", "edad de jubilación este año"]),
 dict(id="F14", area="self-employed", topic="Self-employed contribution brackets 2026",
      current="los tramos de rendimientos y las bases mínimas de 2026 son los mismos que en 2025 (tabla reducida tramo 1: "
              "653,59 €; tabla general tramo 1: 950,98 €); la base máxima general sube a 5.101,20 €; las cuotas suben "
              "ligeramente porque el MEI pasa del 0,8 % al 0,9 %", since="2026-03-31",
      old="una tabla nueva de tramos y cuotas para 2026 (la propuesta retirada) o subidas generales de cuota por tramos",
      boe=[ref("BOE-A-2026-7296", r"Tramos de rendimientos netos 2026 – Euros/mes Base mínima – Euros/mes Base máxima – Euros/mes Tabla reducida\. Tramo 1 ≤ 670 653,59 718,94")],
      boe_old=[ref("BOE-A-2025-3780", r"Tramos de rendimientos netos 2025 – Euros/mes Base mínima – Euros/mes Base máxima – Euros/mes Tabla reducida Tramo 1 ≤ 670 653,59 718,94")],
      cur=[r"(tramos|bases|tablas?)[^.]{0,40}(congelad|se mantienen|sin cambios|iguales|mismos|mismas|prorrogad)",
           r"(congelad|se mantienen|sin cambios|prorrogad)[^.]{0,40}(tramos|bases|tablas?)", r"mismas? (tablas?|bases|tramos) que (en )?2025"],
      oldrx=[r"(nueva tabla|nuevos tramos)[^.]{0,80}2026", r"(suben|subirán|aumentan|se incrementan) (las )?cuotas[^.]{0,40}(entre|hasta) \d"],
      q=["cuota de autónomos 2026", "suben las cuotas de autónomos en 2026", "cuánto paga un autónomo al mes 2026", "cuota mínima autónomos 2026"]),
 dict(id="F15", area="housing", topic="Single Rental Register (short-term lets): obligation annulled",
      current="no hay obligación estatal de registro: el Tribunal Supremo anuló los preceptos del RD 1312/2024 sobre el "
              "registro único y la inscripción para obtener número de registro (sentencias de 19-may, 21-may y 1-jun-2026, "
              "BOE de 8-jun, 26-jun y 18-jul-2026); siguen los registros autonómicos de vivienda turística", since="2026-06-08",
      old="registro único estatal obligatorio desde el 1-jul-2025 (RD 1312/2024, texto original)",
      boe=[ref("BOE-A-2026-12300", r"Anular los preceptos del Real Decreto impugnado referidos al procedimiento de registro único de arrendamientos y la obligación de la inscripción en el Registro de la Propiedad o en el de Bienes Muebles para obtener un numero de registro"),
           ref("BOE-A-2026-13893", r"declarándose nulos los artículos 2"),
           ref("BOE-A-2026-15677", r"declarándose nulos los siguientes preceptos y apartados del citado real decreto")],
      boe_old=[ref("BOE-A-2024-26931", r"entrará en vigor el día 2 de enero de 2025, desplegando efectos sus disposiciones el 1 de julio de 2025")],
      cur=[r"\banul", r"\bnul(o|a|os|as|idad)\b", r"tribunal supremo", r"\bsupremo\b", r"ya no (es|son) obligatori"],
      oldrx=[r"(registro [úu]nico|n[úu]mero de registro|c[óo]digo (de registro|[úu]nico))[^.]{0,80}(es|son|ser[áa]|resulta) obligatori",
             r"(es|son|ser[áa]|resulta) obligatori[oa][^.]{0,80}(registro [úu]nico|n[úu]mero de registro|c[óo]digo [úu]nico)"],
      q=["registro único de arrendamientos es obligatorio", "número de registro alquiler de temporada",
         "registro único alquiler turístico desde cuándo"]),
 dict(id="F16", area="housing", topic="2% cap on rent updates: no cap in force at any reading (case study)",
      current="no hay tope del 2 % en ninguna lectura: el RDL 8/2026 se derogó el 30-abr-2026; el RDL 26/2026 (BOE 30-sep, en "
              "vigor 1-oct) lo reintrodujo y el Congreso lo derogó el 2-oct-2026 (BOE extraordinario núm. 245, PDF de las "
              "14:59:41 UTC), antes de la primera lectura (19:32 UTC)", since="2026-10-02",
      old="afirmar que el tope del 2 % está vigente (RDL 8/2026 o RDL 26/2026)",
      boe=[ref("BOE-A-2026-9359", r"derogaci[oó]n del Real Decreto-ley 8/2026"),
           ref("BOE-A-2026-20526", r"acordó derogar el Real Decreto-ley 26/2026, de 29 de septiembre")],
      boe_old=[ref("BOE-A-2026-6545", r"sin que la variación anual de la renta pueda exceder del dos por ciento"),
               ref("BOE-A-2026-20266", r"En ausencia de este nuevo pacto entre las partes, el incremento de la renta a aplicar no podrá ser superior al dos por ciento")],
      cur=[r"derog", r"no (fue )?convalid", r"decay", r"tumb", r"ya no (est[aá] )?(vigente|en vigor)", r"no est[aá] (vigente|en vigor)", r"no sigue vigente"],
      oldrx=[r"(?<![\d,.])2\s*%", r"dos por ciento"],
      q=["límite subida alquiler 2026", "cuánto puede subir el alquiler este año",
         "tope del 2% alquiler sigue vigente", "actualización renta alquiler 2026 límite"]),
 dict(id="F17", area="housing", topic="State Housing Plan in force",
      current="Plan Estatal de Vivienda 2026-2030 (RD 326/2026, BOE 23-abr-2026)", since="2026-04-23",
      old="Plan Estatal 2022-2025",
      boe=[ref("BOE-A-2026-8872", r"Real Decreto 326/2026, de 22 de abril, por el que se regula el Plan Estatal de Vivienda 2026-2030")],
      boe_old=[],
      cur=[r"2026\s*[-–‑/]\s*2030", r"326/2026"], oldrx=[r"2022\s*[-–‑/]\s*2025", r"42/2022"],
      q=["plan estatal de vivienda vigente", "plan estatal de vivienda ayudas alquiler", "nuevo plan estatal de vivienda", "plan estatal de vivienda 2026"]),
 dict(id="F18", area="justice", topic="Mandatory ADR attempt (MASC) before civil suits",
      current="desde el 3-abr-2025 intentar un MASC es requisito de procedibilidad en la jurisdicción civil (LO 1/2025)",
      since="2025-04-03", old="voluntario / no exigido",
      boe=[ref("BOE-A-2025-76", r"no se exigirá actividad negociadora previa como requisito de procedibilidad"),
           ref("BOE-A-2025-76", r"La presente ley entrará en vigor a los tres meses de su publicación")],
      boe_old=[],
      cur=[r"requisito de procedibilidad", r"obligatori", r"orgánica 1/2025", r"3 de abril de 2025"],
      oldrx=[r"(mediaci[oó]n|masc|negociaci[oó]n previa)[^.]{0,25}(es|son|sigue siendo) (totalmente )?voluntari", r"no es obligatorio (intentar|acudir|pasar)"],
      q=["es obligatorio intentar mediación antes de demandar", "MASC obligatorio antes de ir a juicio",
         "medios adecuados de solución de controversias desde cuándo", "qué es el requisito de procedibilidad MASC"]),
 dict(id="F19", area="justice", topic="Courts of first instance turned into Tribunales de Instancia",
      current="desde el 31-dic-2025 todos los juzgados unipersonales se han transformado en secciones de los tribunales de instancia (LO 1/2025)",
      since="2025-12-31", old="juzgados de primera instancia como órganos vigentes / implantación futura",
      boe=[ref("BOE-A-2025-76", r"El día 31 de diciembre de 2025, los restantes Juzgados, no comprendidos en los supuestos anteriores, se transformarán en las respectivas Secciones")],
      boe_old=[],
      cur=[r"tribunal(es)? de instancia", r"31 de diciembre de 2025", r"secci[oó]n(es)? civil"],
      oldrx=[r"juzgados? de primera instancia"],
      q=["qué son los tribunales de instancia", "siguen existiendo los juzgados de primera instancia",
         "tribunales de instancia cuándo entran en funcionamiento"]),
 dict(id="F20", area="consumer", topic="Customer-service phone wait limit (Ley 10/2025)",
      current="el 95 % de las llamadas debe atenderse en menos de 3 minutos de media (Ley 10/2025, empresas de servicios básicos y grandes empresas); en vigor el 28-dic-2025, con doce meses para que las empresas de su ámbito se adapten (hasta el 28-dic-2026, disposición transitoria única); recurso de inconstitucionalidad 2331/2026 pendiente contra varios artículos",
      since="2025-12-28", old="sin límite legal / ley en tramitación",
      boe=[ref("BOE-A-2025-26698", r"sean atendidas, de media, en un plazo inferior a tres minutos"),
           ref("BOE-A-2025-26698", r"deberán adaptar sus servicios de atención a la clientela a las disposiciones de la misma en el plazo de doce meses desde su entrada en vigor")],
      boe_old=[],
      cur=[r"\b3 minutos", r"tres minutos", r"ley 10/2025"],
      oldrx=[r"proyecto de ley", r"anteproyecto", r"en tramitaci[oó]n", r"cuando se apruebe"],
      q=["tiempo máximo de espera atención al cliente por teléfono", "ley atención al cliente 3 minutos",
         "ley de servicios de atención a la clientela en vigor", "cuánto tiempo pueden tenerme esperando al teléfono atención al cliente"]),
 dict(id="F21", area="consumer", topic="Deadline to answer consumer complaints (Ley 10/2025, TRLGDCU art. 21.3)",
      current="15 días: el art. 21.3 TRLGDCU, modificado por la Ley 10/2025 (en vigor 28-dic-2025), obliga a todas las empresas a "
              "responder en un máximo de quince días (antes, un mes); las empresas del ámbito de la Ley 10/2025 deben resolver en "
              "15 días hábiles, con adaptación hasta el 28-dic-2026; salvo normativa sectorial", since="2025-12-28",
      old="un mes (art. 21.3 TRLGDCU anterior)",
      boe=[ref("BOE-A-2007-20555", r"en todo caso, en el plazo máximo de quince días desde la presentación de la reclamación", con=True),
           ref("BOE-A-2025-26698", r"en todo caso, en el plazo máximo de quince días hábiles desde su presentación")],
      boe_old=[ref("BOE-A-2007-20555", r"en todo caso, en el plazo máximo de un mes desde la presentación de la reclamación", con=True)],
      cur=[r"\b15 d[ií]as", r"quince d[ií]as"], oldrx=[r"(plazo|m[áa]ximo)[^.]{0,40}(de )?(un|1) mes\b", r"\b30 d[ií]as"],
      q=["plazo para responder una reclamación de un consumidor",
         "cuánto tiempo tiene una empresa para contestar una reclamación",
         "plazo máximo respuesta reclamación atención al cliente"]),
 dict(id="F22", area="consumer", topic="Right to be attended by a person (Ley 10/2025)",
      current="derecho a una atención personalizada prestada por personas, no solo por sistemas automáticos (Ley 10/2025); en vigor el 28-dic-2025, con doce meses para que las empresas de su ámbito se adapten (hasta el 28-dic-2026, disposición transitoria única); recurso de inconstitucionalidad 2331/2026 pendiente contra varios artículos",
      since="2025-12-28", old="sin obligación legal general / ley en tramitación",
      boe=[ref("BOE-A-2025-26698", r"la clientela pueda acceder, si así lo desea, a una atención personalizada por parte de la empresa, que deberá ser prestada por personas")],
      boe_old=[],
      cur=[r"atenci[oó]n personalizada", r"(hablar|atendid[oa]s?) (con|por) una persona", r"ley 10/2025", r"atenci[oó]n humana"],
      oldrx=[r"proyecto de ley", r"anteproyecto", r"en tramitaci[oó]n", r"no (hay|existe) (ninguna )?(obligaci[oó]n|ley)"],
      q=["derecho a hablar con una persona atención al cliente",
         "las empresas están obligadas a atender por una persona y no por una máquina",
         "atención al cliente con persona obligatoria ley"]),
 dict(id="F23", area="traffic", topic="Connected V-16 beacon replaces warning triangles",
      current="desde el 1-ene-2026 solo vale la baliza V-16 conectada; los triángulos ya no sirven como señal V-16 (RD 159/2021)",
      since="2026-01-01", old="triángulos válidos / V-16 obligatoria en el futuro",
      boe=[ref("BOE-A-2021-4194", r"Hasta el 1 de enero de 2026 se podrán seguir utilizando como señal V-16", con=True)],
      boe_old=[],
      cur=[r"1 de enero de 2026", r"(ya no|dejan de|dejaron de)[^.]{0,30}(v[aá]lid|servir|ser legales)", r"\bconectada"],
      oldrx=[r"(puedes|se pueden|podr[aá]s|pueden) (seguir )?(usar|utilizar|llevar) (los )?tri[aá]ngulos", r"tri[aá]ngulos[^.]{0,40}(siguen siendo|son) (v[aá]lidos|obligatorios|legales)"],
      q=["son obligatorios los triángulos de emergencia", "baliza V16 obligatoria desde cuándo",
         "puedo seguir usando los triángulos en 2026", "triángulos de emergencia 2026"]),
 dict(id="F24", area="traffic", topic="Compulsory insurance for e-scooters (VMP)",
      current="seguro de responsabilidad civil obligatorio para vehículos personales ligeros desde el 2-ene-2026 (Ley 5/2025)",
      since="2026-01-02", old="no obligatorio",
      boe=[ref("BOE-A-2025-15424", r"Lo establecido en la disposición adicional primera entrará en vigor el 2 de enero de 2026"),
           ref("BOE-A-2025-15424", r"estará obligado a suscribir y mantener en vigor un contrato de seguro")],
      boe_old=[],
      cur=[r"\bobligatori", r"2 de enero de 2026", r"ley 5/2025"], oldrx=[r"no es obligatori", r"no (es|son) necesari"],
      q=["es obligatorio el seguro para patinete eléctrico", "seguro obligatorio patinetes desde cuándo",
         "necesito seguro para mi patinete eléctrico", "seguro patinete eléctrico 2026"]),
 dict(id="F25", area="mobility", topic="Workplace sustainable-mobility plans: deadline cut to 12 months (RDL 7/2026)",
      current="planes de movilidad sostenible al trabajo obligatorios en centros de más de 200 personas trabajadoras o 100 por turno "
              "en el plazo de doce meses desde la entrada en vigor de la Ley 9/2025 (5-dic-2025), es decir desde el 5-dic-2026 "
              "(art. 26.1 modificado por el RDL 7/2026, en vigor 22-mar-2026, convalidado el 26-mar-2026)", since="2026-03-22",
      old="veinticuatro meses (hasta diciembre de 2027), texto original de la Ley 9/2025; o sin obligación / proyecto de ley",
      boe=[ref("BOE-A-2026-6544", r"«1\. En el plazo de doce meses desde la entrada en vigor de esta ley, las empresas"),
           ref("BOE-A-2026-7125", r"acordó convalidar el Real Decreto-ley 7/2026")],
      boe_old=[ref("BOE-A-2025-24545", r"deberán disponer de planes de movilidad sostenible al trabajo para aquellos centros de trabajo con más de 200 personas trabajadoras o 100 por turno")],
      cur=[r"\b(12|doce) meses", r"diciembre de 2026", r"\b7/2026"],
      oldrx=[r"\b(24|veinticuatro) meses", r"diciembre de 2027", r"proyecto de ley", r"anteproyecto"],
      q=["plan de movilidad sostenible obligatorio empresas", "ley de movilidad sostenible obligaciones empresas",
         "plan de movilidad al trabajo cuántos trabajadores"]),
 dict(id="F26", area="invoicing", topic="Verifactu deadline, companies",
      current="1-ene-2027 para contribuyentes del Impuesto sobre Sociedades (RDL 15/2025)", since="2025-12-03",
      old="1-ene-2026",
      boe=[ref("BOE-A-2025-24446", r"deberán tener adaptados los sistemas informáticos a las características y requisitos establecidos en este reglamento y en su normativa de desarrollo antes del 1 de enero de 2027")],
      boe_old=[ref("BOE-A-2023-24840", r"antes del 1 de enero de 2026", con=True)],
      cur=[r"enero de 2027", r"\b2027\b"], oldrx=[r"enero de 2026"],
      q=["cuándo es obligatorio verifactu para sociedades", "verifactu fecha obligatoria", "verifactu 2026 obligatorio", "verifactu se ha aplazado"]),
 dict(id="F27", area="invoicing", topic="Verifactu deadline, self-employed and others",
      current="1-jul-2027 para el resto de obligados (autónomos) (RDL 15/2025)", since="2025-12-03",
      old="1-jul-2026",
      boe=[ref("BOE-A-2025-24446", r"El resto de obligados tributarios mencionados en el artículo 3\.1 deberán tener operativos los citados sistemas informáticos antes del 1 de julio de 2027")],
      boe_old=[ref("BOE-A-2023-24840", r"antes del 1 de julio de 2026", con=True)],
      cur=[r"julio de 2027"], oldrx=[r"julio de 2026"],
      q=["verifactu autónomos cuándo es obligatorio", "verifactu autónomos fecha", "verifactu autónomos julio"]),
 dict(id="F28", area="invoicing", topic="Mandatory B2B e-invoicing regulation (RD 238/2026)",
      current="reglamento aprobado (RD 238/2026, BOE 31-mar-2026); obligatoria 12 meses después de la orden ministerial para >8 M€ y 24 meses para el resto",
      since="2026-03-31", old="reglamento pendiente de aprobación / fechas fijas anteriores",
      boe=[ref("BOE-A-2026-7295", r"a\) Doce meses después, para los empresarios y profesionales cuyo volumen de operaciones"),
           ref("BOE-A-2026-7295", r"b\) Veinticuatro meses después, para el resto de los empresarios y profesionales")],
      boe_old=[],
      cur=[r"238/2026", r"\b(12|doce) meses", r"\b(24|veinticuatro) meses", r"orden ministerial"],
      oldrx=[r"\b(1 de )?(enero|julio|octubre) de 202[78]\b", r"(pendiente|a la espera|falta)[^.]{0,30}(reglamento|aprobaci[oó]n)", r"no (se )?ha (sido )?aprobado", r"proyecto de real decreto", r"borrador"],
      q=["factura electrónica obligatoria entre empresas cuándo", "ley crea y crece factura electrónica fecha",
         "factura electrónica obligatoria autónomos", "factura electrónica obligatoria 2026"]),
]

def load(boe_id, con):
    f = BOE / f"{boe_id}{'-con' if con else ''}.txt"
    if not f.exists():
        return None, f
    return re.sub(r"\s+", " ", f.read_text(encoding="utf-8")), f

def check(r):
    t, f = load(r["boe_id"], r["consolidated"])
    if t is None:
        return {**r, "ok": False, "quote": "", "url": ""}
    m = re.search(r["rx"], t)
    src = t.split(" RETRIEVED:")[0].replace("SOURCE: ", "").strip()
    if not m:
        return {**r, "ok": False, "quote": "", "url": src}
    q = t[max(0, m.start() - 60):m.end() + 60].strip()
    return {**r, "ok": True, "quote": "…" + q + "…", "matched": m.group(0), "url": src}

def main():
    bad = 0
    facts_out, rows, queries = [], [], []
    for f in F:
        f = dict(f)
        f["boe"] = [check(r) for r in f["boe"]]
        f["boe_old"] = [check(r) for r in f["boe_old"]]
        if f["id"] == "F12" and f["boe_old"] and f["boe_old"][0]["ok"]:
            nums = re.findall(r"[\d.]+,\d\d", f["boe_old"][0]["matched"])
            f["old"] = "jubilación con 65 años en 2025: " + " / ".join(nums) + " €/año (con cónyuge a cargo / sin cónyuge / cónyuge no a cargo)"
            f["old_rx_note"] = "old patterns derived from the 2025 BOE annex"
            monthly = [f"{float(n.replace('.', '').replace(',', '.')) / 14:.2f}".replace(".", ",") for n in nums]
            f["old_patterns"] = [r"\b" + n.replace(".", "") + r"\b" for n in nums + monthly]
        for r in f["boe"]:
            if not r["ok"]:
                bad += 1
                print(f"!! {f['id']} current-rule reference NOT verified: {r['boe_id']} /{r['rx']}/", file=sys.stderr)
        for r in f["boe_old"]:
            if not r["ok"]:
                print(f"(i) {f['id']} old-rule reference not verified: {r['boe_id']} /{r['rx']}/", file=sys.stderr)
        f["cur_patterns"] = f.pop("cur")
        rx = f.pop("oldrx")
        f["old_patterns"] = f.get("old_patterns") or rx
        qs = f.pop("q")
        for i, q in enumerate(qs, 1):
            queries.append({"qid": f"{f['id']}-Q{i}", "fact_id": f["id"], "query": q})
        facts_out.append(f)
        for r in f["boe"] + f["boe_old"]:
            rows.append({"fact_id": f["id"], "role": "current" if r in f["boe"] else "old", "boe_id": r["boe_id"],
                         "consolidated": r["consolidated"], "verified": r["ok"], "url": r.get("url", ""),
                         "quote": r.get("quote", ""), "note": r.get("note", "")})
    (ROOT / "data/facts.json").write_text(json.dumps(facts_out, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(ROOT / "data/facts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(ROOT / "data/queries.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["qid", "fact_id", "query"]); w.writeheader(); w.writerows(queries)
    v = sum(r["verified"] for r in rows)
    print(f"facts={len(facts_out)} queries={len(queries)} boe_refs={len(rows)} verified={v} current_unverified={bad}")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
