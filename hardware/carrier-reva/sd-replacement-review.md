# SD replacement drawing evidence

The current PCB still carries the **held Hirose footprint**. This record recovers
engineering evidence for the proposed direct-mount Würth replacement; it is not
footprint approval or authorization to mix the two footprints.

Manufacturer document: Würth 693071010811, revision 001.002, 2019-01-24,
eight pages. Pages 1–3 were rendered and visually inspected on 2026-10-28.
The document is available through a [distributor mirror](https://285624.selcdn.ru/syms1/iblock/02c/02cb54b580a198e0c05f06d93c8cd97a/072850a20961f306b7b73daa634626dd.pdf);
the [manufacturer URL](https://www.we-online.com/components/products/datasheet/693071010811.pdf)
was indexed but returned HTTP 403 to direct download. Download SHA-256:
`e2859032e66b457131233f9345cd0066d3d0aa012c4782b16cf8f15464801d98`.
No third-party document is relicensed under this repository's MIT license.

The recommended land pattern on page 1 gives 1.10 mm signal pitch, 0.80 × 1.50 mm
signal lands with staggered Y positions, two 1.80 × 1.40 mm lands numbered 10,
and two 1.40 × 1.90 mm lands numbered 9. It is **not** the DM3AT land pattern.
Page 3 identifies a normally closed 9–10 card-detect switch: it opens when the
card is inserted. An existing software assumption of closed-on-insertion would
therefore be wrong if detection is added later. Current firmware does not use
these detect contacts.

Before adoption: derive and independently check every pad coordinate from the
page-1 datum; resolve shielding versus switch connections without assuming the
Hirose SH pin exists; review card access and push/eject travel from page 3;
update both schematic and footprint, replace the held socket, route all SD
connections, and re-run ERC/DRC and assembly review. Do not substitute the
similarly named KiCad 693072010801 footprint: it is a different part.

A PDF linked elsewhere on the Symmetron Hirose product page was also inspected
and rejected: it actually describes **Amtek 5KTFP-08S0NHL02**, not DM3AT. Its
SHA-256 is `7d1737043adae6de6a82ab30a17610ce9cee03f3e8e659c5098375c84a5a5863`.
A product-page link is not sufficient evidence of document identity.
