# Data verification request

These questions come from an audit of the April 13, 2026 exports (`MasterBactSurvey4_13_26.csv`, `MasterChemSurvey4_13_26.csv`). The forecasting models have not been changed; the answers decide which results can be trusted. Line numbers refer to the original export files, counting the header as line 1. Blank columns in each CSV are for your answers.

## 1. Site identity (`site_conflicts.csv`)

9 site codes appear with more than one waterbody name. For each code: is it one physical site throughout its history? If so, what is its authoritative name? A site registry with coordinates and any code changes would answer this fully.

| Site code | Samples | Names used |
| --- | ---: | --- |
| 5303387 | 21 | Forgotten Creek WGC; WGC Sammamish tributary |
| 5303391 | 89 | Piper's Creek; Pipers |
| 5303392 | 94 | Mohlendorph Creek; Molendorph |
| 5303393 | 86 | Venema; Venema Creek; venema |
| 5303394 | 96 | North Creek; Piper's Creek North Creek; Venema |
| 5303395 | 63 | Piper's Creek Viewlands; Viewlands |
| 5303396 | 76 | Piper's Creek Below TP; Pipers |
| 5303397 | 80 | Piper's Creek Above TP; Pipers |
| 5303398 | 88 | Piper's Creek Trib M; Pipers; Trib ""M"" |

## 2. Bacteria calculations (`bacteria_rows_to_review.csv`)

Most reported averages equal `mean(three replicate counts) × 100 / sample volume`. Please confirm that formula and its units, then check the rows that differ:

- ecoli: 12 rows, possible zero floor to one
- ecoli: 7 rows, requires protocol review
- ecoli: 37 rows, within half unit rounding
- other coliform: 79 rows, requires protocol review

Also: is there a reporting floor (zero reported as one), a rounding rule, or a cap on countable colonies?

## 3. Chemistry calculations (`chemistry_rows_to_review.csv`)

Dissolved oxygen averages two replicates; alkalinity is drop count × 5; hardness is drop count × 10. 5 rows do not match. Which value is correct for each?

## 4. Turbidity

| Method recorded | Rows | Numeric values | Values equal to 8 |
| --- | ---: | ---: | ---: |
| (no method recorded) | 2733 | 462 | 31 |
| Turbidity meter | 195 | 190 | 1 |
| Turbidity tube | 293 | 247 | 229 |

Does a tube reading of 8 mean "8 or lower" (a reporting limit)? What method was used where none is recorded?

## 5. Timing

- bacteria: 1818 of 2487 sample times are exactly 00:00; record creation dates fall on 1 calendar date(s).
- chemistry: 2352 of 3221 sample times are exactly 00:00; record creation dates fall on 2 calendar date(s).

Creation dates look like a bulk import, so they cannot show when results became available. Please answer: (a) Are 00:00 times date-only? (b) What timezone are the times in? (c) How many days after collection are bacteria and chemistry results usually available? The models currently assume three days.

## 6. Newer data

An export in the same format covering April 2026 to today would allow current forecasts and a fresh test period.
