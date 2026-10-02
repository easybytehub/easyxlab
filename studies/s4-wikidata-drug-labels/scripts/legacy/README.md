Scripts from the earlier exploratory review (EasyByte Lab "medcard" review, 2026-10-02),
copied verbatim for provenance. They imported a helper `wd.py` that was not preserved;
`../wd.py` is its replacement (same `q()`, `LANGS`, `LF` names). The study pipeline does
not run these files: their logic was generalised in `01_extract_wikidata.py`
(drugs.py/diseases.py/qual.py), `03_detect.py` (qual.py → detector a, vand.py → detector f,
brands.py → detector b) and `02_reference_sources.py`.
