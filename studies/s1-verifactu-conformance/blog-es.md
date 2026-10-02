---
title: "Qué publican en GitHub los proyectos Verifactu de código abierto, y cuánto cumple"
date: 2026-10-02
section: papers
status: borrador
---

# Qué publican en GitHub los proyectos Verifactu de código abierto, y cuánto cumple

Desde el 29 de julio de 2025, quien fabrica un sistema informático de facturación tiene
que poder declarar que cumple el RD 1007/2023 y la Orden HAC/1177/2024. El núcleo de
esa obligación es técnico: cada registro de facturación lleva una huella SHA-256
calculada sobre ocho de sus campos (cinco en un registro de anulación), entre ellos la
huella del registro anterior. Así la secuencia queda encadenada y cualquier alteración
se nota.

Buena parte del software Verifactu que se escribe hoy es pequeño y abierto: módulos
para ERP libres y librerías en PHP, Python, Go, C# o TypeScript. Esos proyectos
publican ejemplos, ficheros de test y salidas de sus generadores, y otros
desarrolladores los copian como referencia. Quisimos saber si esos registros cumplen
la norma y, cuando no, qué reglas fallan.

## Cómo lo hicimos

Recorrimos GitHub con sus dos buscadores: el de código, buscando los elementos del
registro (`RegistroAlta`, `RegistroAnulacion`, `RegistroEvento`…) en ficheros XML, y
el de repositorios, buscando «verifactu». De cada repositorio bajamos todos sus XML,
fijados a un commit. En total, 1.008 repositorios y 29.491 ficheros. Solo 261
contenían algún elemento Verifactu, en 63 repositorios de terceros y en el de nuestra
propia herramienta, que excluimos.

Antes de auditar nada clasificamos cada fichero. No es lo mismo un ejemplo que
pretende ser válido que un test escrito para fallar, una respuesta de la AEAT o una
plantilla con huecos. Solo los primeros cuentan. Después pasamos `verifactu-lint`, la
herramienta de código abierto que mantenemos en EasyByte.

**Dos advertencias.** Primera: EasyByte desarrolla esa herramienta y ofrece servicios
comerciales relacionados con Verifactu. Segunda: el estudio lo han hecho agentes de
IA, de la recogida a la redacción. El agente revisó uno a uno los errores contra el
texto literal de la norma y recalculó cada huella con una implementación independiente.
Ninguna persona experta ha revisado los hallazgos.

## Lo primero: casi nadie publica registros reales

De los 1.008 repositorios que hablan de Verifactu, solo 19 publican al menos un
registro que pretenda ser válido.

La familia más numerosa de lo publicado son plantillas: 91 ficheros con valores de
relleno, la mayoría (62) copias de los ejemplos del documento de la AEAT que describe
el servicio web. Esos ejemplos son ilustrativos y lo dicen a su manera: en la huella
pone literalmente `<Huella>Huella</Huella>` o `<Huella>HuellaRegistroAnterior</Huella>`,
y el NIF es `AAAA` o `NNNN`. Muchos están guardados en carpetas `tests/`, `fixtures/` o
`examples/`, al lado de los ficheros de prueba de verdad.

No es un error de quien los copia, ni de la AEAT. Pero un test que «parsea el ejemplo
oficial» pasa igual tanto si el cálculo de la huella del proyecto está bien como si no.

## Lo segundo: unas tres de cada diez referencias reales fallan

Quedaron 35 ficheros que sí pretenden ser registros válidos: 21 altas, 4 anulaciones y
11 eventos. De ellos, 10 tienen al menos un error (28,6 %; intervalo de confianza del
95 %: 16,3–45,1 %), 4 tienen algún aviso y 15 no tienen ningún hallazgo.

Por repositorios, 6 de los 19 (31,6 %; IC 95 %: 15,4–54,0 %) publican al menos un
registro de referencia con algún error, siempre en un fichero que no aparece en ningún
repositorio más antiguo del corpus. Con 19 repositorios los intervalos son anchos y no
se puede afinar más.

## La huella, de lejos

El error más repetido, en 5 de los 19 repositorios, es una huella declarada que no
coincide con la que sale de los campos del propio registro. Las causas que pudimos
reconstruir son poco espectaculares:

- Una huella copiada de la documentación de la AEAT y puesta en un registro con otros
  datos.
- Un generador que escribe la huella en minúsculas, cuando la AEAT pide hexadecimal en
  mayúsculas, y que además genera la fecha y hora sin huso horario.
- Una anulación escrita con los nombres de elemento de un alta: los campos que entran
  en la huella quedan vacíos.

Un sexto repositorio usa una estructura inventada que no se parece al esquema oficial,
con la huella metida en un elemento que no existe. De ahí salen el resto de errores de
la tabla: falta de identificación del sistema, del tipo de factura o del desglose.
Hubo además una cuota que no sale de su base y su tipo, y una factura completa (F1) sin
destinatario, que la AEAT exige.

Los errores de huella no se detectan validando contra el XSD: el esquema comprueba que
haya un campo `Huella` de hasta 64 caracteres, no sabe calcular un SHA-256. Y la propia
AEAT no rechaza el registro: según sus validaciones, devuelve «un aviso de error (no
generará rechazo)». El registro entra, marcado, y solo lo ve quien lo envía.

## Lo que no está en los ejemplos

**La cadena casi no aparece.** De los 35 ficheros válidos, 34 contienen un solo
registro, y 11 vienen de un mismo repositorio. Los ejemplos XML públicos casi nunca
contienen una cadena, así que no sirven de referencia para ella. No medimos si los
proyectos prueban el encadenamiento en su código.

**No hay ejemplos hechos para fallar.** En ninguno de los 63 repositorios de terceros
encontramos un registro deliberadamente inválido, guardado para comprobar que un
validador lo rechaza. Los cuatro que nuestra primera clasificación tomó por tests
negativos resultaron ser ficheros de referencia positivos.

## Sobre la herramienta

El agente revisó los 22 errores y no encontró ningún falso positivo. No son 22 casos
independientes: 10 salen de dos ficheros del mismo generador. Contando las 12
situaciones distintas (repositorio y regla), la tasa de falsos positivos queda por
debajo del 24 % con un 95 % de confianza; no se puede afirmar que sea cero. La
implementación independiente la escribió el mismo equipo: descarta fallos de
programación, no una lectura equivocada compartida de la especificación.

Sí encontramos seis mejoras para `verifactu-lint`. Hay dos huecos de cobertura: no
revisa el formato de las fechas ni si la hora lleva huso horario. Dos diagnósticos
engañosos. Un aviso que debería ser «no determinable», y una mejora de usabilidad. Los
publicamos con el estudio: encontrar los límites del propio instrumento también es un
resultado.

## Límites

Los buscadores de GitHub no lo ven todo: solo la rama principal, ficheros de menos de
384 KB y, en general, ningún fork. Lo que se publica como ejemplo no es lo que un
sistema emite en producción: el estudio mide las referencias que circulan, no la
facturación de nadie. La herramienta cubre solo una parte de la norma, así que las
tasas de error son cotas inferiores.

## Qué haría falta

Ninguna corrección individual cambiaría mucho este panorama. Falta un conjunto
compartido y con licencia abierta de cadenas de varios registros: unas válidas y otras
rotas a propósito, cada una con el error que debe producir. Así cada proyecto podría
comprobar su generador contra algo más exigente que un ejemplo con la palabra «Huella»
donde debería ir un hash.

*Método, datos agregados y scripts: estudio S1 de EasyByte Lab. Los repositorios
aparecen anonimizados y no se ha contactado a sus mantenedores.*
