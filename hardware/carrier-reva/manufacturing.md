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
report lists remaining return-path exceptions; zero DRC is not their approval.

`tools/export_carrier_reva.py --out <new-directory>` exports fabrication
**candidates**, parses each Gerber/drill independently with gerbv, and records
hashes plus raster inspections. These are explicitly not order releases.
`tools/package_carrier_reva.py --mode fabrication --out <new-directory>` adds
fail-closed release checks. Review mode remains available for unfinished work.
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

A delivered quote is **not yet available**: final source release and the delivery
postcode/address are still required. Do not present a promotional small-board
price or a generic shipping estimate as a quote for this 160 × 210 mm board.
