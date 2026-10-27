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

## Full available-catalog comparison

The follow-up [geometry check](../../tools/check_sd_geometry.py) now compares all
14 lands (eight SD, two detect, four shield) and all five footprint exclusions
against page 3's dimensions. It uses pin-1 centre X and the bottom edge of the
signal lands as explicit datums; the [report](../../reports/sd-geometry.json)
records the derived bounds. The lower-right exclusion is conservatively extended
to the lower shield-land edge. This closes the available-catalog comparison,
but not the inaccessible engineering drawing's revision approval.

At the actual 180° placement, the socket mouth is at board Y=29.875 mm and the
ejected card tip reaches Y=24.275 mm. The board edge is Y=20 mm. Thus the ejected
card extends beyond the copper hold at Y=28 mm and still sits inside the board
outline. Reserve the card/access strip to the north edge; do not put parts or
an enclosure wall there based only on the copper hold. The assembly locator now
marks this separate mechanical reservation. Finger access and enclosure fit
remain physical checks.

The comparison also exposed a mounting conflict: H2 at (176,24) mm overlapped
the access envelope (including a 6.4 mm head/courtyard allowance). It is moved to
(157,24) mm in the provisional board. The new geometry test rejects restoration
of the old hole position. These remain provisional mounting points, not an
established PC1715 enclosure pattern.
