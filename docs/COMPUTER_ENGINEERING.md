# Computer Engineer track

Open `/tracks/cpe`. Code: `backend/app/services/cpe_lab.py`, `auto_elec.py`, `routers/cpe.py` (`/api/cpe/...`), `frontend/.../panels/CpePanel.tsx`. Manual: 8 steps and 21 quiz questions in `backend/app/content`.

Sources: a computer-engineering course deck (843 pages: computer technology, networking, logic, DC circuits, digital electronics, electrical engineering, operating systems, programming languages, data structures, architecture) and twelve diagrams (zonal architecture, dashboard harness, harness, keyless entry, airbag SRS, 360 camera, automotive Ethernet, EV high voltage, AC and DC charging, networking devices, a key-fob photo).

## Tabs
- **Numbers**: base conversion, two's complement, signed overflow, IEEE 754.
- **Logic**: truth tables, minimal sum of products (Quine-McCluskey), equivalence checks.
- **Circuits**: Ohm's law, series and parallel, divider with load, LED resistor, RC time, colour code.
- **Architecture**: cache tag/index/offset, AMAT, CPU time, Amdahl, pipeline, RAID.
- **Vehicle wiring**: wire, drop and fuse; harness checker; CAN bus load and termination.
- **EV**: AC and DC charge time, pack layout, pre-charge, insulation check.
- **Systems reference**: eight vehicle systems with checks and safety limits, a bus comparison, and the mistakes found.

## Rules of thumb (not standards)
Wire ratings, the 3% drop target, the 125% fuse rule, 70% CAN load, 90% AC efficiency, the DC taper model and the per-volt insulation limits are starting points. The wire maker's table, the vehicle's service manual and the current regulation win.

## Mistakes found
See `SLIPS` in each service (shown in the app). Examples: the deck's "one's complement" steps include "add 1"; IPv6 "IPSec is mandatory"; ground treated as earth; the DC charging diagram titled CHAdeMO/CCS draws a CCS inlet with CAN (CCS uses power-line communication); Level 1/2 labels with a Type 2 inlet; inconsistent wire colours across diagrams; "Doar Control Module".

## Not built
Hardware work (breadboard, meter, scope, FPGA), a full CPU or logic simulator, vehicle diagnosis, key programming, immobilizer bypass, relay or signal capture, and work on airbag or high-voltage circuits. The deck was sampled, not read slide by slide.

## Simulators and vehicle decoders

Open `/tracks/cpe` > Simulators or Vehicle decoders.

- Logic circuit: a netlist of gates and flip-flops with a waveform per input row.
- Tiny CPU: four registers, 64 bytes of memory, flags Z N C, with a count of pipeline hazards.
- Circuit solver: resistors, voltage and current sources and capacitors (DC and charge/discharge over time).
- Cache trace: hit or miss for each address, with first-touch, capacity or conflict reasons.
- CAN signals (Intel and Motorola byte order), J1939 IDs, DTCs, OBD-II PIDs, diagnostic (ISO-TP/UDS) frames, charge pilot duty and voltage, plug proximity resistor.

Not built: Verilog, analog simulation beyond simple DC and RC, inductors, a real instruction set, and sending anything onto a real vehicle bus. Each service lists the mistakes found in its sources (`SLIPS`).
