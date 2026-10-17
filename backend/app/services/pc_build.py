"""PC build lab: compatibility check, power supply sizing, build and first-boot checklist, and a no-POST diagnostic.
Reference and planning only. It cannot see your parts: always confirm against the maker's spec sheets and the motherboard's QVL and manual."""
from __future__ import annotations

import re

NOTE = "Planning aid based on common rules. Confirm every part against the manufacturer's spec page and the motherboard manual before buying or building."


class PcError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# socket -> RAM types a board with that socket may use (the board decides: a given board takes one type only)
SOCKETS = {
    "AM4": ["DDR4"], "AM5": ["DDR5"], "LGA1200": ["DDR4"], "LGA1700": ["DDR4", "DDR5"], "LGA1851": ["DDR5"], "LGA1151": ["DDR4"], "TR4/sTRX4": ["DDR4"],
}
FORM = {"E-ATX": 4, "ATX": 3, "Micro-ATX": 2, "Mini-ITX": 1}   # a case fits its size and smaller
PSU_SIZES = [350, 450, 550, 650, 750, 850, 1000, 1200, 1600]


def _num(v, name, lo=0, hi=100000, req=True):
    if v in (None, ""):
        if req:
            raise PcError(f"{name} is needed.")
        return 0.0
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise PcError(f"{name} must be a number.") from None
    if not lo <= x <= hi:
        raise PcError(f"{name} must be between {lo:g} and {hi:g}.")
    return x


def options() -> dict:
    return {"sockets": {k: v for k, v in SOCKETS.items()}, "form_factors": list(FORM), "psu_sizes": PSU_SIZES, "note": NOTE}


def check(s: dict) -> dict:
    """Compare chosen parts. Blank fields are skipped. Returns problems (will not work), warnings (check this) and passes."""
    bad, warn, ok = [], [], []
    cs, bs = str(s.get("cpu_socket") or "").strip(), str(s.get("board_socket") or "").strip()
    if cs and bs:
        (ok if cs.lower() == bs.lower() else bad).append(f"CPU socket {cs} and motherboard socket {bs} " + ("match." if cs.lower() == bs.lower() else "do not match. The CPU will not fit or run. Pick a board with the same socket."))
    br, rr = str(s.get("board_ram") or "").upper().strip(), str(s.get("ram_type") or "").upper().strip()
    if br and rr:
        (ok if br == rr else bad).append(f"Board takes {br} and the RAM is {rr}: " + ("match." if br == rr else "they are not interchangeable. Buy RAM of the board's type."))
    if bs in SOCKETS and br and br not in SOCKETS[bs]:
        warn.append(f"{bs} boards normally use {' or '.join(SOCKETS[bs])}, but you entered {br}. Recheck the board's spec page.")
    bf, cf = str(s.get("board_form") or ""), str(s.get("case_form") or "")
    if bf in FORM and cf in FORM:
        (ok if FORM[bf] <= FORM[cf] else bad).append(f"{bf} board in a case rated for {cf}: " + ("fits." if FORM[bf] <= FORM[cf] else "the board is bigger than the case supports."))
    g, gm = _num(s.get("gpu_len_mm"), "GPU length", 0, 500, False), _num(s.get("case_gpu_mm"), "Case GPU clearance", 0, 600, False)
    if g and gm:
        (bad if g > gm else warn if g > gm - 15 else ok).append(f"GPU {g:.0f} mm in {gm:.0f} mm of clearance: " + ("too long." if g > gm else "tight; leave room for cables and front fans." if g > gm - 15 else "fits."))
    c, cm = _num(s.get("cooler_mm"), "Cooler height", 0, 250, False), _num(s.get("case_cooler_mm"), "Case cooler clearance", 0, 250, False)
    if c and cm:
        (bad if c > cm else ok).append(f"Air cooler {c:.0f} mm in {cm:.0f} mm: " + ("too tall; the side panel will not close." if c > cm else "fits."))
    rad = str(s.get("radiator") or "").strip()
    if rad and not str(s.get("case_rad") or "").strip():
        warn.append("You listed a radiator but not the sizes your case supports. Check the case spec for front, top and rear radiator support.")
    ct, gt = _num(s.get("cpu_tdp"), "CPU power", 0, 600, False), _num(s.get("gpu_tdp"), "GPU power", 0, 1000, False)
    psu = _num(s.get("psu_w"), "Power supply watts", 0, 3000, False)
    if psu and (ct or gt):
        need = recommend_psu(ct, gt, int(_num(s.get("ssd"), "SSDs", 0, 20, False)), int(_num(s.get("hdd"), "Hard drives", 0, 20, False)), int(_num(s.get("fans"), "Fans", 0, 30, False)), int(_num(s.get("ram_sticks"), "RAM sticks", 0, 16, False) or 2))
        (bad if psu < need["estimated_load_w"] else warn if psu < need["recommended_w"] else ok).append(
            f"Power supply {psu:.0f} W vs estimated load {need['estimated_load_w']} W (recommended {need['recommended_w']} W): " +
            ("too small; it will shut down under load." if psu < need["estimated_load_w"] else "workable but little headroom for spikes and aging." if psu < need["recommended_w"] else "enough."))
    gp = str(s.get("gpu_power_connector") or "").strip().lower()
    if gp and gp not in ("none", "") and not str(s.get("psu_cables") or "").strip():
        warn.append(f"Your GPU needs {gp}. Confirm the power supply has that connector or the right adapter, and never daisy-chain a high-power card on one cable.")
    if str(s.get("cpu_cooler_socket") or "").strip() and cs and cs.lower() not in str(s.get("cpu_cooler_socket")).lower():
        bad.append(f"The cooler lists {s.get('cpu_cooler_socket')} but the CPU socket is {cs}. Check the cooler's mounting kit.")
    if not (bad or warn or ok):
        raise PcError("Fill in at least a pair of parts to compare, like CPU socket and motherboard socket.")
    return {"problems": bad, "warnings": warn, "passes": ok, "verdict": "Do not buy as listed: fix the problems first." if bad else "No hard conflicts found. Read the warnings." if warn else "Everything entered is compatible.",
            "also_check": ["BIOS version supports your CPU (the board may need a BIOS update, sometimes without a CPU installed).", "M.2 slot type (NVMe or SATA) and which SATA ports it disables.", "RAM on the board's QVL, speed and capacity limits.",
                           "Front-panel USB-C and USB header support in the case.", "Cooler mounting for your socket and RAM height clearance."], "note": NOTE}


def recommend_psu(cpu_w, gpu_w, ssd=1, hdd=0, fans=4, sticks=2) -> dict:
    cw, gw = _num(cpu_w, "CPU power", 0, 600, False), _num(gpu_w, "GPU power", 0, 1000, False)
    other = 50 + sticks * 5 + ssd * 5 + hdd * 10 + fans * 3
    load = cw + gw + other
    rec = load * 1.4          # typical efficiency sweet spot is about half to 70% load, plus room for transient spikes
    size = next((s for s in PSU_SIZES if s >= rec), PSU_SIZES[-1])
    return {"cpu_w": cw, "gpu_w": gw, "other_w": other, "estimated_load_w": round(load), "recommended_w": size,
            "why": "About 40% headroom for spikes and aging, which also keeps the supply near its efficient range. Modern GPUs can spike well above their rated power for a split second.",
            "buy_tips": ["Choose a reputable 80 Plus rated unit from a maker with independent reviews.", "Check connectors: CPU 8-pin (or 4+4), PCIe 6+2 or 12VHPWR for the GPU, SATA, and enough modular cables.", "Do not reuse the cables from a different brand of modular supply.", "The estimate is a plan, not a measurement. Use the maker's recommended wattage for your exact GPU."], "note": NOTE}


BUILD_STEPS = [
    {"phase": "Before you start", "steps": ["Clear a big, clean, non-carpeted table with good light. Keep the motherboard box as an anti-static surface.", "Check parts against the order and run the compatibility check. Photograph labels and serial numbers.",
                                          "Update plan: note the board's BIOS version requirement for your CPU.", "Ground yourself by touching bare metal on the case, and handle parts by the edges."]},
    {"phase": "Outside the case", "steps": ["Install the CPU: align the triangle, never force it, and never touch the pins or pads.", "Latch the socket, then mount the cooler with fresh thermal paste (pea size) or the pre-applied pad, tightened evenly in a cross pattern.",
                                           "Seat RAM in the slots your manual names for two sticks, until both clips click.", "Install the M.2 SSD with its screw and remove any plastic film on the thermal pad."]},
    {"phase": "Inside the case", "steps": ["Install the I/O shield (if separate) and the right standoffs for your board size, no extras.", "Mount the board, then the power supply with the fan toward the vent.", "Connect CPU power (8-pin) and the 24-pin main power firmly.",
                                          "Install the GPU in the top x16 slot and connect its power cables from separate runs where possible.", "Connect front panel header: power switch, reset, LEDs (see the manual diagram), USB and audio headers.", "Connect fans to the right headers and cable-manage away from fans."]},
    {"phase": "First boot", "steps": ["Plug the monitor into the graphics card, not the motherboard (if you have a card).", "Power on. A first boot with a new RAM kit can take a minute while memory trains.", "Enter BIOS (Delete or F2). Confirm the CPU, RAM amount and speed, and drive are seen. Enable XMP or EXPO for rated RAM speed.",
                                   "Update the BIOS if the board needs it, using the maker's method.", "Install the operating system from a USB drive, then chipset and graphics drivers."]},
    {"phase": "Burn-in and handoff", "steps": ["Check temperatures at idle and under a CPU and GPU load test for 20 to 30 minutes. Watch for throttling and unexpected shutdowns.", "Run a memory test (for example a full pass) and check drive health.", "Set a fan curve if too loud.",
                                             "Record the parts list, serials, BIOS version and passwords in a handoff sheet. Keep the box and receipts for warranty.", "Give the client a backup plan and recovery media."]},
]

NOPOST = [
    {"id": "nothing", "match": "no power nothing dead no fans no lights", "title": "Nothing happens at all", "checks": ["Confirm the wall outlet works and the power supply switch is on I (not O).", "Check the 24-pin and CPU power cables are fully clicked in.", "Test the case power button header: briefly short the two power switch pins with a screwdriver. If it starts, the case button or header wiring is the issue.", "Remove everything except CPU, one RAM stick and the power supply to the board; try again.", "Try the paperclip test on a spare PSU only (a PSU test tool is safer). Swap in a known-good supply if you can.", "Check for a stray standoff shorting the board, and a bent socket pin on the board."]},
    {"id": "fans-no-display", "match": "fans spin no display black screen no signal", "title": "Fans spin but no picture", "checks": ["Make sure the monitor cable is in the graphics card, not the board, and try another cable or monitor input.", "Reseat the GPU and its power cables.", "Reseat RAM; try one stick in the slot your manual recommends, then try each stick alone.", "Clear CMOS (battery out for 5 minutes, or the jumper/button) in case the BIOS held bad settings.", "Check the CPU 8-pin is plugged in and the cooler is mounted without being over-tightened.", "Wait a few minutes after a new RAM kit: first boot memory training can be slow.", "Test with the integrated graphics if the CPU has it, and with another GPU."]},
    {"id": "led", "match": "qled debug led cpu dram vga boot light stuck", "title": "A debug LED stays on (CPU, DRAM, VGA or BOOT)", "checks": ["CPU: reseat the CPU and cooler, check the 8-pin, and confirm the BIOS supports the CPU.", "DRAM: reseat RAM, try one stick per slot, lower to the board's default speed, clear CMOS.", "VGA: reseat the GPU and power, try another PCIe slot or cable.", "BOOT: the system sees hardware but no bootable drive; check the drive connection, boot order and that the OS install is intact."]},
    {"id": "beeps", "match": "beeps beep codes long short", "title": "Beep codes", "checks": ["Look up your board's or BIOS maker's code in the manual: patterns differ between AMI, Award and Phoenix.", "As a general rule, repeated short beeps point to RAM or power, and one long and two short to video.", "Reseat RAM and GPU first, then test with minimum parts."]},
    {"id": "restart", "match": "restart loop boot loop reboots shuts down random crash", "title": "Restarts, boot loops or shuts down", "checks": ["Check temperatures: a poor cooler mount or missing thermal paste causes quick thermal shutdowns.", "Reduce RAM to one stick and disable XMP/EXPO to rule out memory.", "Test with a known-good power supply: weak or failing supplies cause resets under load.", "Check front panel reset header wiring and a stuck reset button.", "Run a memory test and update the BIOS."]},
    {"id": "no-usb", "match": "no keyboard usb not working bios", "title": "USB devices not working", "checks": ["Try the rear ports directly on the board, one device at a time.", "Check the front panel USB header orientation.", "Reset BIOS settings and try a PS/2 or different keyboard.", "Update the chipset driver in the OS."]},
    {"id": "no-drive", "match": "no drive ssd nvme not detected boot device", "title": "Drive not detected", "checks": ["Reseat the M.2 or SATA cable and power.", "Check the M.2 slot shares lanes with SATA ports and that the drive type (NVMe or SATA) is supported in that slot.", "Check BIOS storage settings and update BIOS.", "Test the drive in another machine or enclosure to rule out the drive."]},
    {"id": "hot", "match": "hot overheating temperature throttle loud fan", "title": "Runs hot or loud", "checks": ["Confirm cooler contact and paste, and that the cooler fan or pump is spinning.", "Improve airflow: front intake, rear and top exhaust, filters cleaned.", "Set a sensible fan curve in BIOS, and check for dust.", "Check the power plan and that boost behavior is normal for the CPU."]},
]


def diagnose(symptom: str) -> dict:
    q = re.sub(r"[^a-z0-9 ]", " ", (symptom or "").lower())
    toks = [t for t in q.split() if len(t) > 2]
    if not toks:
        raise PcError("Describe what the computer does, like 'fans spin but no display'.")
    scored = sorted(((sum(1 for t in toks if t in n["match"].split() or t in n["title"].lower()), n) for n in NOPOST), key=lambda x: -x[0])
    best = [n for s, n in scored if s][:2] or [next(n for n in NOPOST if n["id"] == "fans-no-display")]
    return {"matches": best, "rule": "Strip to the minimum: CPU with cooler, one RAM stick, power, and graphics. Add one part at a time. Change one thing at a time.",
            "safety": "Unplug the power supply and press the power button to drain it before touching internal parts. Do not open a power supply.", "note": NOTE}


def checklist() -> dict:
    return {"phases": BUILD_STEPS, "note": NOTE}
