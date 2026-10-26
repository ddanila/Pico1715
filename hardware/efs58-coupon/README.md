# Four-contact EFS experiment

This is a buildable **contact test fixture**, not a replacement 202-58 connector.
It separates the uncertain spring-contact fit from the large connector body and
Pico1715 electronics. C1–C4 are fixture identifiers, **not X1/X2 pin numbers**.
Nothing here connects to power, Pico, FPGA, or the carrier.

The selected experiment uses four loose **Mill-Max 1001-0-15-15-30-27-04-0**
receptacles on a 2.5 × 2.5 mm grid. Their documented outside dimensions allow
us to design the holder now. Their round-pin rating does **not** qualify an EFS
blade; thickness alone, including the recalled 0.3 mm figure, cannot establish
that fit. Measure width, thickness and insertion length on a sacrificial EFS
male contact before inserting it. Do not use the motherboard as the first test.

## Files

* `front.stl` and one of `body_c15.stl`, `body_c25.stl`, `body_c35.stl`:
  print-ready parts in millimetres, minimum Z at the print bed. Suffixes are
  **diametral** clearances above nominal socket diameters: 0.15/0.25/0.35 mm.
* Matching STEP files preserve assembly Z coordinates; `assembly.step` includes
  the nominal socket envelopes and PCB slab. Socket springs are not modelled.
* `coupon.kicad_sch`, `coupon.kicad_pcb`, local symbol/footprint libraries:
  four isolated routed paths on a 28 × 30 mm, two-layer, 1.6 mm FR4 board.
* `fabrication/`: Gerbers and separate plated/non-plated Excellon drills for
  **this test PCB only**. No production carrier order is implied.
* `parameters.json`: sourced contact dimensions and our design choices.
  `cad-checks.json` records solid and mesh checks; `validation.json` records
  checked file hashes. `measurements.csv` is an intentionally blank bench log.
* `drawing.svg`: orientation, stack and assembly instructions.

## Why this contact

| Candidate | Evidence and decision |
| --- | --- |
| Loose Mill-Max 1001, #30 contact | **Selected for experiment.** Published geometry, straight solder tail, individual small-quantity stock listing; no special crimp tool. Flat-blade compatibility still unknown. |
| Harwin M20-1180042 / generic Dupont | M20 specifies a 0.64 mm square mating pin. Generic parts have no controlled spring geometry. Not evidence of grip on a thin EFS blade. |
| Harwin M80-013 | Documented 0.46–0.51 mm round-pin system; crimp tooling adds expense without resolving blade compatibility. |
| DIN 41612 donor | A modified DIN male fitting an EFS female does not prove the reverse pairing. Tail dimensions such as 0.3 mm are not a female mating specification. |
| Original EFS female donor | Best baseline for comparison. Exact contact retention and extraction must be measured; do not assume EFS26 and EFS58 contacts have identical retention bodies. |

Sources: [Mill-Max manufacturer's metric catalogue](https://www.mill-max.com/sites/default/files/external/catalog/2021-02/153M-201M.pdf),
printed p165 / PDF p17; [Harwin M20](https://www.harwin.com/products/M20-1180042);
[Harwin M80 drawing](https://cdn.harwin.com/pdfs/M80-013.pdf).
The EFS 2.5 mm mating grid comes from TGL 29331/03, p2 Fig.1; the original
angled female has **5 mm PCB-tail spacing**, which this straight test fixture
does not reproduce. See the [EFS evidence review](../carrier/efs58/investigation.md).
Source PDF SHA-256 for the Mill-Max catalogue:
`ca75ed3c0f2ca1b360a38616e2883a8fcdfbfc3defccbdc877a0b3c76338f663`.
Original CAD/code are MIT; manufacturer documents remain with their owners.

## Small shopping list

| Item | Quantity | Notes |
| --- | ---: | --- |
| Mill-Max 1001-0-15-15-30-27-04-0 | 10 | Four installed, six for single-contact trials/spares |
| M2 × 12 mm machine screws | 2 | With four small washers and two nuts; tighten lightly |
| Printed front | 1 | Non-conductive, tough resin preferred |
| Printed bodies | 3 | One of each clearance for calibration; only one assembled |
| Coupon PCB | 1 | 1.6 mm FR4, standard two-layer service; no assembly stencil needed |
| Thin insulated hookup wire | 4 lengths | Optional test leads soldered to TP1–TP4 |
| Sacrificial original EFS male contacts and known-good female | A few | Grip/depth reference; do not destroy a working rare board |

On 2026-10-26, the [Mouser listing](https://www.mouser.com/ProductDetail/Mill-Max/1001-0-15-15-30-27-04-0)
returned small-quantity stock and USD 0.68 each / USD 5.91 for ten. This is a
research snapshot, not an Estonia VAT/shipping-inclusive quote. Shipping, PCB
minimum order and printing can dominate; combine with an existing order. Buy
only test quantities before proving fit. A full 58-contact build is not yet a
qualified or costed production connector.

## Print and assemble

1. Print all three body variants. The exported body has its open pocket face on
   the bed, bores vertical and screw feet at the top. Keep supports out of bores.
   The front is also exported mating face down; compensate elephant's foot and
   inspect/clear holes without widening the retaining lip. A 0.4 mm FDM
   nozzle is a poor first choice: the thinnest nominal pocket web is 0.37 mm.
   Resin capability and shrinkage still require a sample, not a promised fit.
2. Check a **loose** socket against a sacrificial EFS blade before assembly.
   Reject binding, absent spring grip, scoring or plastic deformation. A circular
   pin rating is not a diagonal-based qualification for a rectangle. If it fails,
   stop this contact branch and select a different spring contact/donor insert.
3. Drop four sockets into a body from its open pocket face, tails toward the PCB.
   The front plate captures the flanges. Align the clipped corner on both pieces
   with `KEY` on the PCB; fit screws through front, body and PCB into the nuts.
   The socket entrance sits 1 mm behind the front surface. Never use the front
   plate as an insertion-depth stop for an unknown EFS pin length.
4. Choose the smallest clearance that lets all sockets settle without force.
   The holder is a clearance fit, **not** the manufacturer's 1.45 mm press-fit
   installation. Screw clamping and soldered tails provide retention. Small axial
   float is intentional; do not fill socket pockets with adhesive or solder.
   Body bores are open through the rear; the flange shoulder takes insertion
   load, avoiding a fragile printed membrane under each socket.
5. Fit PCB with its silkscreen facing the holder. Integral feet leave 0.4 mm under
   the body for pads/fillets. Solder tails from the back, briefly, checking that
   print material does not soften. Wire TP pads as desired. No precision crimp
   tool is required. The PCB has no ground plane or common electrical node.

Nominal tail end is Z=8.37 mm; PCB occupies Z=5.9–7.5 mm, giving 0.87 mm nominal
tail protrusion (0.61 mm with both catalogue length tolerances subtracted).
Board-thickness tolerance and actual seating must still be checked. The maximum
nominal-pocket radial float is 0.175 mm; a large printing-clearance variant is
for calibration, not evidence that this alignment error is acceptable in service.

The fixture has broad fastening ears and **cannot be pushed into a fully
populated EFS male connector**: it would collide with neighbouring pins. Use
loose sacrificial pins held independently, or a separate donor populated only
at the four test positions. Do not cut or bend motherboard pins for this test.
No host insertion-depth stop, keying or 58-contact case clearance is claimed.

## Bench acceptance and next decision

Record dimensions, blade orientation, free insertion length, selected clearance,
printer/material, force, resistance and observations in `measurements.csv`.
Blank cells mean **not measured**. Start with one socket, then all four.

* Confirm each Jn reaches only TPn; all six pairs of channels must remain isolated.
* Compare insertion/withdrawal force with a known-good original contact using
  the same pin. Reject deformation or unstable grip before repeated cycling.
* If a four-wire meter is available, measure contact resistance separately from
  the PCB/wires. The manufacturer's 10 mΩ rating is for its qualified mating
  conditions; it is not a claim for this EFS pairing. A continuity beep alone
  does not qualify a bus connector.
* Try 20 gentle cycles as an initial screen, rechecking movement-sensitive
  continuity, resistance and retention. Passing this screen does not establish
  the original connector's durability rating or a current rating for our print.

Only after this succeeds: choose the contact, measure the host blade depth and
shroud/keying, then extend the insert to 58 positions and design the full adapter.
The original carrier X2 footprint hold stays in force. Making a complete shell
around an unqualified contact now would lock in the riskiest assumption.

## Regenerate and verify

From the repository root, with FreeCAD and KiCad installed:

```sh
FreeCADCmd tools/generate_efs58_coupon_cad.py
/usr/bin/python3 tools/generate_efs58_coupon_pcb.py
python3 tools/draw_efs58_coupon.py
make test-efs58-coupon-cad
make export-efs58-coupon
make test-efs58-coupon
```

On this workstation substitute `/snap/bin/freecad.cmd` for `FreeCADCmd`.
`test-efs58-coupon-cad` means KiCad ERC/DRC/parity; FreeCAD geometry checks run
inside the model generator. Portable tests check released STL topology, dimensions,
channel connectivity, tolerance arithmetic and evidence freshness without CAD tools.
