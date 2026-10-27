# SD land-pattern evidence

The manufacturer-authored [Hirose DM3 catalog](https://media.ret.hu/datasheet/DM3_Catalog_D49662_en.pdf),
printed March 1, 2025, page 3, was downloaded and visually inspected on
2026-10-27. The [review record](../../reports/sd-catalog-review.json) records its
hash and the limited confirmed dimensions. The third-party mirror hosts a
manufacturer document; no copy is redistributed here.

The catalog confirms DM3AT-SF-PEJM5 pin functions, 1.1 mm signal pitch and
0.7 × 1.2 mm signal lands, matching the installed KiCad footprint. It also shows
hatched areas marked “No conductive traces.” The footprint carries five F.Cu
exclusions; their complete datum/dimension comparison is still pending.
Detection lands 9/10 are library identifiers, not additional SD bus pins.

The current engineering drawing (0000947170, EDC-325165-00-00) could not be
visually retrieved: the manufacturer download returned HTTP 403, and the
Farnell mirror timed out. PDF metadata alone is not a dimensional review.
Consequently the all-layer hold and all 12 J3 opens remain. To close it, obtain
a readable drawing, compare all shield/detect lands and exclusion boundaries,
check the rotated placement's ejection envelope, then route and rerun DRC.
