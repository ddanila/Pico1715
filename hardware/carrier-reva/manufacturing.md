# Carrier prototype manufacturing specification

Quantity: **five bare boards**, no stencil or assembly service initially. Assemble
one first. Board outline 160 × 210 mm, nominal thickness 1.6 mm, four layers,
ENIG. Order is not authorized by this document. Reserve daughterboard and EFS58
adapter are separate items; neither is included in the carrier quantity.

Target stack-up: **JLC04161H-7628**, as listed in the
[manufacturer stack-up catalog](https://jlcpcb.com/impedance), checked 2026-10-28.
From top: 35 µm copper / 0.2104 mm 7628 prepreg / 15.2 µm copper /
1.065 mm core / 15.2 µm copper / 0.2104 mm prepreg / 35 µm copper.
The two inner layers are GND. Nominal mask above copper is 0.01524 mm.
Catalog verification is separate from the supplier accepting this stack-up for
the actual order. No controlled-impedance value is specified or claimed.

Use supplied Gerbers and separate plated/non-plated Excellon files. Do not scale,
mirror, omit inner planes or substitute connector footprints. J6 finished holes
are 1.10 mm; J7 holes are 0.95 mm and must finish within 0.90–1.00 mm. Verify the
supplier's finished-hole tolerance against that range before placing an order.
Signal vias remain 0.60/0.30 mm (pad/drill) in the reviewed candidate. The routing
report now has zero return-path exceptions across all 408 signal vias.

`tools/export_carrier_reva.py --out <new-directory>` exports fabrication
**candidates**, parses each Gerber/drill independently with gerbv, and records
hashes plus raster inspections. These are explicitly not order releases.
`tools/package_carrier_reva.py --mode fabrication --candidate <inspected-directory> --out <new-directory>` adds
fail-closed release checks and copies the exact inspected bytes without re-exporting.
Changes to source files or any export invalidate the candidate. Review mode remains
available for unfinished work.
Never upload a review/candidate directory as an approved order package.

Release requires current net parity/interlock checks, fresh ERC and DRC with
zero violations and zero opens, all return transitions meeting the 4 mm target,
reviewed plane gaps and assembly access, independent fabrication inspection,
source-matched evidence and a clean committed checkout. Physical host mating,
current-limited power/isolation checks, analyzer capture and boot/write verification
are later qualification stages, not evidence that can be manufactured on a desk.

## Quote worksheet

Request five boards with the dimensions, stack-up and finish above, shipping to
Estonia. Record the exact fabrication manifest hash, quote date/expiry, board
price, engineering/finish surcharges, shipping service and price, VAT, handling,
and delivered total/currency. Obtain confirmation of the 0.95 mm finished-hole
tolerance. Buy the BOM for one assembly first, adding spare small passives and
one spare SD socket if inexpensive. Leave J7 unpopulated unless testing reserve.

A final delivered quote is **not yet available**. The supplied delivery postcode
is kept in the local worksheet. The 2026-10-28 public calculator estimate for
Estonia is **EUR 96.70 boards + EUR 24.09 DHL Express**, 0.70 kg, 2–4 transit
business days plus 3–4 production days. Board charges: 22.44 engineering,
18.40 finish, 18.67 board, 37.18 precision holes (display rounding differs by
one cent from the total). No coupons are assumed.

Applying the [Estonian standard VAT rate of 24%](https://www.emta.ee/en/business-client/taxes-and-payment/value-added-tax/vat-rates-and-supply-exempt-tax/standard-vat-rate)
to boards plus shipping gives a **planning estimate of EUR 149.78**, excluding
any handling fees. This is a calculation, not a supplier checkout total. The
public calculator did not verify the postcode-specific charges, tax collection,
or the actual Gerbers. Obtain those before purchase. No order is authorized.

## Finished-hole process selection

The [supplier capability table](https://jlcpcb.com/capabilities/Capabilities),
checked 2026-10-28, lists ordinary PTH tolerance +0.13/−0.08 mm and a precision
“press-fit holes” option ±0.05 mm for circular 0.55–2.0 mm holes on multilayer
ENIG boards, identified in PCB remarks. Select that precision process for **J7
pins 1–3 only**, nominal 0.95 mm, at board coordinates (164,100), (166.5,100),
(169,100) mm. These remain soldered JST pins; “press-fit” is the supplier's
process name, not an assembly instruction. Confirm acceptance and surcharge in
the actual quotation. Ordinary tolerance is unsuitable for the documented range.

Supplier capability evidence is not order-specific acceptance. Keep that gate
open until the quoted process explicitly includes these three holes. J6 nominal
1.10 mm holes with drawing tolerance ±0.15 mm accommodate the ordinary range.

## Power-path screening and SD decoupling

`power-review.json` now follows conductive paths from each supply input to its
loads, including plated vias, rather than summing unrelated branches. The
assumed rail budgets are 1 A for RAW, 0.5 A for Pico VSYS, 0.2 A for Pico 3V3
and 0.1 A for the FPGA-fed logic rail. They are screening assumptions, not
measured consumption or regulator ratings. The worst modeled drops are about
57 mV to the FPGA power input, 13 mV from the diode output to Pico VSYS,
6 mV on the SD rail, and 21 mV on the logic rail. Connector/cable, diode, ground
return, regulator headroom, temperature and SD transient losses remain to be
added before supply qualification.

C19 is moved to (166.5, 46.6) mm, rotated 270 degrees, with a direct 0.5 mm
power branch and a nearby 0.6/0.3 mm ground via. Its power pad is approximately
6.15 mm from the SD power pad, outside the socket body/courtyard. This reduces
the previous roughly 12 mm separation. Fresh ERC/DRC pass; socket mating and
SD transient behavior still require the first assembled board.

## Completed layout desk review

All signal via returns meet 4 mm after rerouting F_A2/F_A3/F_A12/F_A15,
F_RFSH_N and F_IEO and adding local GND transitions. Clock/write copper remains
unchanged at 169.863/183.176 mm with 11/10 vias. There are 195 supplemental
GND vias. Fresh ERC/DRC has zero violations and zero opens.

`assembly-review.json` records the planar assembly and local plane-gap review,
with independent Gerber enlargements under `reports/carrier-reva-inspection`.
The four short screening flags are local antipad boundaries/openings. They are
reviewed geometry, not proof of signal integrity. Inspect all final exports and
retain their hashes before sealing a package. Supplier acceptance remains open.
