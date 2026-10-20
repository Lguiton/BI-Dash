"""Computer Engineer depth: digital design and timing, embedded maths, analog, power, motors, control, PCB, reliability, architecture, datasheet and bench practice."""
from __future__ import annotations

import math
import re

from app.services.prolab import NOTE, ProError, lab, lines, num, r, ref, tool, txt

T = "cpe"
lab(T, "Computer engineering depth: digital design, embedded, analog, power, control, PCB and reliability")


# ------------------------------------------------------------------ digital design
def fsm(a):
    rows = lines(a, "table", "the state table", 2)
    trans: dict[tuple[str, str], tuple[str, str]] = {}
    states: list[str] = []
    inputs: list[str] = []
    for p in rows:
        if len(p) < 3:
            raise ProError("Each line needs: state, input, next state, output (output may be blank).")
        s, i, n = p[0], p[1], p[2]
        o = p[3] if len(p) > 3 else ""
        if (s, i) in trans:
            raise ProError(f"State {s} has two different transitions for input {i}.")
        trans[(s, i)] = (n, o)
        for x in (s, n):
            if x not in states:
                states.append(x)
        if i not in inputs:
            inputs.append(i)
    missing = [f"{s} on {i}" for s in states for i in inputs if (s, i) not in trans]
    reach, todo = {states[0]}, [states[0]]
    while todo:
        cur = todo.pop()
        for i in inputs:
            n = trans.get((cur, i), (None, ""))[0]
            if n and n not in reach:
                reach.add(n)
                todo.append(n)
    unreachable = [s for s in states if s not in reach]
    outs = {o for _, o in trans.values()}
    mealy = len({trans[(s, i)][1] for (s, i) in trans if s == s}) > 1 and any(len({trans[(s, i)][1] for i in inputs if (s, i) in trans}) > 1 for s in states)
    bits = max(1, math.ceil(math.log2(len(states))))
    enc = {s: format(k, f"0{bits}b") for k, s in enumerate(states)}
    code = [f"// State encoding ({bits} bits): " + ", ".join(f"{s}={enc[s]}" for s in states),
            "always @(posedge clk or posedge reset) begin", f"  if (reset) state <= {bits}'b{enc[states[0]]};", "  else case (state)"]
    for s in states:
        code.append(f"    {bits}'b{enc[s]}: begin  // {s}")
        for i in inputs:
            if (s, i) in trans:
                code.append(f"      if (in == {i}) state <= {bits}'b{enc[trans[(s, i)][0]]};")
        code.append("    end")
    code += ["    default: state <= " + f"{bits}'b{enc[states[0]]};  // recover from illegal states", "  endcase", "end"]
    return {"states": len(states), "inputs": inputs, "state_bits": bits, "missing_transitions": missing or ["none"], "unreachable_states": unreachable or ["none"],
            "style": "Mealy (output depends on state and input)" if mealy else "Moore-style (output depends on the state)" if len(outs) > 1 else "no outputs listed",
            "verilog": "\n".join(code), "tips": ["The first state listed is the reset state.", "Every state needs a transition for every input, or the hardware holds its state.", "Use a default branch so illegal states recover.", "Separate the state register, next-state logic and output logic for clean timing."]}


tool(T, "fsm_check", "State machine check", "Check a state table and draft the Verilog.", [("table", "Lines of: state, input, next state, output", "IDLE,0,IDLE,0\nIDLE,1,RUN,0\nRUN,0,IDLE,1\nRUN,1,RUN,0", "area")], fsm)


def timing(a):
    T_, tcq, tl, tlmin, tsu, th, sk = (num(a, k, lo=0) for k in ("period_ns", "clk_to_q_ns", "logic_max_ns", "logic_min_ns", "setup_ns", "hold_ns", "skew_ns"))
    setup = T_ + sk - tcq - tl - tsu
    hold = tcq + tlmin - th - sk
    fmax = 1000 / (tcq + tl + tsu - sk) if (tcq + tl + tsu - sk) > 0 else None
    return {"setup_slack_ns": r(setup, 3), "hold_slack_ns": r(hold, 3), "max_clock_mhz": r(fmax, 1) if fmax else None,
            "verdict": "Meets both setup and hold." if setup >= 0 and hold >= 0 else ("Setup fails: slow the clock or shorten the logic path." if setup < 0 else "") + (" Hold fails: add delay on the short path (slowing the clock does not fix hold)." if hold < 0 else ""),
            "how": "Setup slack = period + skew - clock-to-Q - longest logic - setup. Hold slack = clock-to-Q + shortest logic - hold - skew. Skew is positive when the capture clock arrives later."}


tool(T, "timing_slack", "Setup and hold timing", "Check setup and hold slack and the fastest clock.", [("period_ns", "Clock period (ns)", 10), ("clk_to_q_ns", "Clock to Q (ns)", 0.5), ("logic_max_ns", "Longest logic path (ns)", 6), ("logic_min_ns", "Shortest logic path (ns)", 0.3), ("setup_ns", "Setup time (ns)", 0.4), ("hold_ns", "Hold time (ns)", 0.3), ("skew_ns", "Clock skew (ns)", 0.1)], timing)


def cpi(a):
    base, bf, mr, pen, lf, lp, ls = num(a, "base_cpi", lo=0.1), num(a, "branch_pct", lo=0, hi=100) / 100, num(a, "mispredict_pct", lo=0, hi=100) / 100, num(a, "mispredict_penalty_cycles", lo=0), num(a, "load_pct", lo=0, hi=100) / 100, num(a, "load_use_stall_pct", lo=0, hi=100) / 100, num(a, "load_use_stall_cycles", lo=0)
    mhz = num(a, "clock_mhz", lo=1)
    br, ld = bf * mr * pen, lf * lp * ls
    eff = base + br + ld
    return {"effective_cpi": r(eff, 3), "branch_stall_cpi": r(br, 3), "load_use_stall_cpi": r(ld, 3), "mips": r(mhz / eff, 1), "slowdown_vs_ideal": r(eff / base, 2),
            "advice": ["Better branch prediction or a shorter pipeline cuts the branch term.", "Forwarding (bypassing) removes most data-hazard stalls; a load-use stall of 1 cycle usually remains.", "Compare designs by time per program = instructions x CPI / clock, not by clock alone."]}


tool(T, "pipeline_cpi", "Pipeline CPI with hazards", "Effective CPI and MIPS with branch and load-use stalls.", [("base_cpi", "Ideal CPI", 1), ("branch_pct", "Branches (% of instructions)", 20), ("mispredict_pct", "Mispredicted (% of branches)", 10), ("mispredict_penalty_cycles", "Mispredict penalty (cycles)", 15), ("load_pct", "Loads (% of instructions)", 25), ("load_use_stall_pct", "Loads followed by a use (%)", 40), ("load_use_stall_cycles", "Load-use stall (cycles)", 1), ("clock_mhz", "Clock (MHz)", 1000)], cpi)


def vmem(a):
    va, pg, pte, tlb = int(num(a, "va_bits", lo=16, hi=64)), num(a, "page_kb", lo=0.5), num(a, "pte_bytes", lo=1), int(num(a, "tlb_entries", lo=1))
    ob = int(math.log2(pg * 1024))
    if 2 ** ob != int(pg * 1024):
        raise ProError("Page size must be a power of two (for example 4).")
    vpn = va - ob
    per_page = int(pg * 1024 // pte)
    lv = math.ceil(vpn / math.log2(per_page)) if per_page > 1 else None
    return {"offset_bits": ob, "virtual_page_number_bits": vpn, "single_level_table_mb": r(2 ** vpn * pte / 1048576, 2), "entries_per_page_table": per_page, "levels_needed": lv, "tlb_reach_kb": r(tlb * pg, 1),
            "why": "A single flat table for a big address space is huge, so tables are split in levels that each fit one page. The TLB caches recent translations; its reach is entries x page size."}


tool(T, "vmem_plan", "Virtual memory and TLB", "Page table size, levels and TLB reach.", [("va_bits", "Virtual address bits", 48), ("page_kb", "Page size (KB)", 4), ("pte_bytes", "Page table entry (bytes)", 8), ("tlb_entries", "TLB entries", 64)], vmem)


def amat(a):
    h1, m1, h2, m2, mem, tm, tp = (num(a, k, lo=0) for k in ("l1_hit_ns", "l1_miss_pct", "l2_hit_ns", "l2_miss_pct", "memory_ns", "tlb_miss_pct", "tlb_penalty_ns"))
    v = h1 + m1 / 100 * (h2 + m2 / 100 * mem) + tm / 100 * tp
    return {"amat_ns": r(v, 3), "without_tlb_ns": r(v - tm / 100 * tp, 3), "tip": "AMAT = L1 hit + L1 miss x (L2 hit + L2 miss x memory) + TLB miss x penalty. A small miss rate times a big penalty dominates."}


tool(T, "amat", "Average memory access time", "Two-level cache plus TLB.", [("l1_hit_ns", "L1 hit (ns)", 1), ("l1_miss_pct", "L1 miss (%)", 5), ("l2_hit_ns", "L2 hit (ns)", 5), ("l2_miss_pct", "L2 miss (%)", 20), ("memory_ns", "Memory (ns)", 80), ("tlb_miss_pct", "TLB miss (%)", 0.5), ("tlb_penalty_ns", "TLB miss penalty (ns)", 30)], amat)


# ------------------------------------------------------------------ embedded
def uart(a):
    clk, baud, ov = num(a, "clock_hz", lo=1), num(a, "baud", lo=1), int(num(a, "oversample", lo=1))
    div = max(1, round(clk / (ov * baud)))
    act = clk / (ov * div)
    err = 100 * (act - baud) / baud
    return {"divisor": div, "actual_baud": r(act, 1), "error_pct": r(err, 3), "verdict": "Fine: under 2% error." if abs(err) < 2 else "Marginal: 2 to 3% can work on short clean links." if abs(err) < 3 else "Too far off: pick a different clock (for example 11.0592 MHz) or oversampling."}


tool(T, "uart_baud", "UART baud divisor", "Divisor and baud error for a clock.", [("clock_hz", "Peripheral clock (Hz)", 16000000), ("baud", "Wanted baud", 115200), ("oversample", "Oversampling (16 usual)", 16)], uart)


def timer(a):
    clk, f, bits = num(a, "clock_hz", lo=1), num(a, "target_hz", lo=0.001), int(num(a, "bits", lo=8, hi=32))
    best = None
    for p in range(1, 65537):
        arr = round(clk / (p * f))
        if 1 <= arr <= 2 ** bits:
            act = clk / (p * arr)
            e = abs(act - f) / f
            if best is None or e < best[0] - 1e-12:
                best = (e, p, arr, act)
                if e == 0:
                    break
    if not best:
        raise ProError("No prescaler and period fit that frequency: use a larger timer or a slower target.")
    return {"prescaler": best[1], "period_ticks": best[2], "actual_hz": r(best[3], 4), "error_pct": r(best[0] * 100, 5), "note2": "Counts to the period value, then fires. Register values are often prescaler-1 and period-1: check your chip's manual."}


tool(T, "timer_setup", "Timer prescaler and period", "Best prescaler and period for a target frequency.", [("clock_hz", "Timer clock (Hz)", 16000000), ("target_hz", "Wanted rate (Hz)", 1000), ("bits", "Timer width (bits)", 16)], timer)


def i2c(a):
    vdd, cb = num(a, "vdd", lo=1, hi=6), num(a, "bus_pf", lo=1)
    mode = txt(a, "mode").lower()
    tr = {"standard": 1000, "fast": 300, "fast+": 120}.get(mode)
    if not tr:
        raise ProError("Mode must be standard, fast or fast+.")
    mx = tr * 1e-9 / (0.8473 * cb * 1e-12)
    mn = (vdd - 0.4) / 0.003
    return {"pullup_max_ohm": r(mx, 0), "pullup_min_ohm": r(mn, 0), "suggested_ohm": r(math.sqrt(mx * mn), 0) if mx > mn else None,
            "verdict": "Pick a value between min and max (a standard 4.7k, 2.2k or 1k)." if mx > mn else "No resistor works: the bus is too slow for this capacity. Slow the bus or cut capacitance (shorter wires, fewer devices).",
            "how": "Max from the allowed rise time and bus capacitance: Rp <= tr / (0.8473 x Cb). Min so a device can pull the line low with 3 mA: Rp >= (Vdd - 0.4 V) / 3 mA."}


tool(T, "i2c_pullup", "I2C pull-up resistor", "Allowed range for the SDA and SCL pull-ups.", [("vdd", "Supply (V)", 3.3), ("bus_pf", "Bus capacitance (pF)", 100), ("mode", "Speed: standard, fast or fast+", "fast")], i2c)


# ------------------------------------------------------------------ analog
def adc(a):
    n, vref = int(num(a, "bits", lo=1, hi=32)), num(a, "vref", lo=0.1, strict=True)
    fs = num(a, "sample_rate_hz", lo=1)
    lsb = vref / 2 ** n
    out = {"lsb_mv": r(lsb * 1000, 4), "levels": 2 ** n, "ideal_snr_db": r(6.02 * n + 1.76, 1), "nyquist_hz": r(fs / 2, 1)}
    sinad = a.get("sinad_db", "").strip()
    if sinad:
        out["enob_bits"] = r((float(sinad) - 1.76) / 6.02, 2)
    out["tips"] = ["Signals above half the sample rate fold back as false lower frequencies (aliasing): filter before the ADC.", "Real converters lose 1 to 3 bits to noise: use the ENOB from the data sheet (from SINAD).", "Noise below one LSB cannot be seen; averaging N samples gains about half a bit per 4x samples."]
    return out


tool(T, "adc_budget", "ADC resolution and ENOB", "Step size, ideal SNR, Nyquist and effective bits.", [("bits", "Bits", 12), ("vref", "Reference (V)", 3.3), ("sample_rate_hz", "Sample rate (Hz)", 100000), ("sinad_db", "Measured SINAD (dB, optional)", "")], adc)


def opamp(a):
    k = txt(a, "kind").lower()
    rf, rin, gbw, vin = num(a, "rf_ohm", lo=0, strict=True), num(a, "rin_ohm", lo=0, strict=True), num(a, "gbw_hz", lo=1), num(a, "vin", lo=-1000)
    if k not in ("inverting", "noninverting"):
        raise ProError("Kind must be inverting or noninverting.")
    g = -rf / rin if k == "inverting" else 1 + rf / rin
    noise_gain = 1 + rf / rin
    return {"gain": r(g, 3), "gain_db": r(20 * math.log10(abs(g)), 2), "bandwidth_hz": r(gbw / noise_gain, 0), "output_v": r(g * vin, 3),
            "tips": ["Bandwidth shrinks as gain grows: gain-bandwidth product / noise gain.", "Check the output cannot swing beyond the supply rails (clipping).", "A feedback resistor from kilo-ohms to tens of kilo-ohms balances noise and loading."]}


tool(T, "opamp_gain", "Op-amp gain and bandwidth", "Inverting or non-inverting stage.", [("kind", "inverting or noninverting", "inverting"), ("rf_ohm", "Feedback resistor (ohm)", 100000), ("rin_ohm", "Input resistor (ohm)", 10000), ("gbw_hz", "Gain-bandwidth product (Hz)", 1000000), ("vin", "Input voltage (V)", 0.1)], opamp)


def rcfilter(a):
    R, C, f = num(a, "r_ohm", lo=0, strict=True), num(a, "c_nf", lo=0, strict=True) * 1e-9, num(a, "test_hz", lo=0)
    fc = 1 / (2 * math.pi * R * C)
    att = -10 * math.log10(1 + (f / fc) ** 2)
    ph = -math.degrees(math.atan(f / fc))
    out = {"cutoff_hz": r(fc, 2), "gain_at_test_db": r(att, 2), "phase_at_test_deg": r(ph, 1), "time_constant_ms": r(R * C * 1000, 4)}
    as_, fs_ = a.get("stop_db", "").strip(), a.get("stop_hz", "").strip()
    if as_ and fs_:
        n = math.ceil(math.log10((10 ** (float(as_) / 10) - 1) / (10 ** 0.03 - 1)) / (2 * math.log10(float(fs_) / fc)))
        out["butterworth_order_needed"] = n
    out["note2"] = "One RC stage falls 20 dB per decade above cutoff. Higher order (more stages or an active filter) falls faster; Butterworth is flat in the pass band."
    return out


tool(T, "rc_filter", "RC low-pass filter", "Cutoff, attenuation and filter order.", [("r_ohm", "Resistor (ohm)", 1600), ("c_nf", "Capacitor (nF)", 100), ("test_hz", "Frequency to test (Hz)", 5000), ("stop_db", "Wanted attenuation (dB, optional)", ""), ("stop_hz", "...at this frequency (Hz, optional)", "")], rcfilter)


# ------------------------------------------------------------------ power and motors
def conv(a):
    k = txt(a, "kind").lower()
    vin, vo, io, fs, rip, dv = num(a, "vin", lo=0, strict=True), num(a, "vout", lo=0, strict=True), num(a, "iout", lo=0, strict=True), num(a, "fsw_khz", lo=1) * 1000, num(a, "ripple_pct", lo=1, hi=100) / 100, num(a, "vripple_mv", lo=1) / 1000
    if k == "buck":
        if vo >= vin:
            raise ProError("A buck converter lowers voltage: output must be below input.")
        d = vo / vin
        di = rip * io
        L = (vin - vo) * d / (fs * di)
        C = di / (8 * fs * dv)
        ipk = io + di / 2
    elif k == "boost":
        if vo <= vin:
            raise ProError("A boost converter raises voltage: output must be above input.")
        d = 1 - vin / vo
        iin = io / (1 - d)
        di = rip * iin
        L = vin * d / (fs * di)
        C = io * d / (fs * dv)
        ipk = iin + di / 2
    else:
        raise ProError("Kind must be buck or boost.")
    return {"duty_cycle_pct": r(d * 100, 1), "inductor_uh": r(L * 1e6, 2), "output_capacitor_uf": r(C * 1e6, 2), "inductor_peak_current_a": r(ipk, 3),
            "tips": ["Pick an inductor with a saturation current well above the peak, and a standard value at or above this.", "Use low-ESR capacitors: ESR adds ripple the formula leaves out.", "Higher switching frequency means smaller parts but more switching loss.", "Ideal, lossless formulas: expect 80 to 95% efficiency and check the controller data sheet."]}


tool(T, "dcdc_design", "Buck and boost converter", "Duty cycle, inductor and output capacitor.", [("kind", "buck or boost", "buck"), ("vin", "Input (V)", 12), ("vout", "Output (V)", 5), ("iout", "Output current (A)", 2), ("fsw_khz", "Switching frequency (kHz)", 500), ("ripple_pct", "Inductor ripple (% of current)", 30), ("vripple_mv", "Output ripple (mV)", 30)], conv)


def motor(a):
    v, R, kt, tl = num(a, "voltage", lo=0, strict=True), num(a, "resistance_ohm", lo=0, strict=True), num(a, "kt_nm_per_a", lo=0, strict=True), num(a, "load_torque_nm", lo=0)
    stall_i, stall_t, w0 = v / R, kt * v / R, v / kt
    if tl >= stall_t:
        raise ProError(f"The load ({tl} N m) is at or above the stall torque ({r(stall_t, 4)} N m): the motor cannot turn it.")
    i = tl / kt
    w = (v - i * R) / kt
    pin = v * i
    pout = tl * w
    return {"stall_current_a": r(stall_i, 2), "stall_torque_nm": r(stall_t, 4), "no_load_rpm": r(w0 * 60 / (2 * math.pi), 0), "running_rpm": r(w * 60 / (2 * math.pi), 0), "running_current_a": r(i, 3),
            "mechanical_power_w": r(pout, 3), "efficiency_pct": r(100 * pout / pin, 1) if pin else None,
            "tips": ["Size the driver for the stall current, not the running current.", "Use a current limit: a stalled brushed motor can overheat in seconds.", "Add a gearbox to trade speed for torque; efficiency drops a little per stage."]}


tool(T, "dc_motor", "DC motor operating point", "Speed, current and efficiency under a load.", [("voltage", "Supply (V)", 12), ("resistance_ohm", "Winding resistance (ohm)", 2), ("kt_nm_per_a", "Torque constant (N m per A)", 0.03), ("load_torque_nm", "Load torque (N m)", 0.05)], motor)


# ------------------------------------------------------------------ control
def second(a):
    wn, z = num(a, "natural_freq_rad_s", lo=0, strict=True), num(a, "damping_ratio", lo=0)
    if z >= 1:
        kind = "critically damped" if z == 1 else "overdamped (no overshoot, slower)"
        return {"type": kind, "overshoot_pct": 0.0, "settling_time_2pct_s": r(4 / (z * wn), 4) if z < 3 else None, "tips": ["Overdamped is safe but slow.", "A damping ratio of 0.5 to 0.8 is a common target."]}
    wd = wn * math.sqrt(1 - z * z)
    os = 100 * math.exp(-math.pi * z / math.sqrt(1 - z * z))
    return {"type": "underdamped (rings before settling)" if z > 0 else "undamped (never settles)", "overshoot_pct": r(os, 2), "peak_time_s": r(math.pi / wd, 4), "settling_time_2pct_s": r(4 / (z * wn), 4) if z > 0 else None, "rise_time_s_approx": r(1.8 / wn, 4),
            "tips": ["Overshoot depends only on damping ratio; speed depends on natural frequency.", "More gain usually raises natural frequency and lowers damping: watch the overshoot.", "These formulas fit a plain second-order system; real loops have delays and limits."]}


tool(T, "second_order", "Second-order response", "Overshoot, peak and settling time.", [("natural_freq_rad_s", "Natural frequency (rad/s)", 10), ("damping_ratio", "Damping ratio", 0.5)], second)


def zn(a):
    ku, tu = num(a, "ultimate_gain", lo=0, strict=True), num(a, "ultimate_period_s", lo=0, strict=True)
    rows = []
    for name, kp, ti, td in (("P", 0.5 * ku, None, None), ("PI", 0.45 * ku, tu / 1.2, None), ("PID", 0.6 * ku, tu / 2, tu / 8)):
        rows.append({"type": name, "kp": r(kp, 4), "ki": r(kp / ti, 4) if ti else None, "kd": r(kp * td, 4) if td else None})
    return {"gains": rows, "how": "Ziegler-Nichols: raise P gain until the output oscillates steadily (ultimate gain Ku, period Tu), then use these starting values. They tend to overshoot: reduce Kp by a third for a gentler response.", "tips": ["Test in a safe state with limits on output and travel.", "Add an anti-windup limit to the integrator.", "Filter the derivative term: noise gets amplified."]}


tool(T, "pid_zn", "PID from Ziegler-Nichols", "Starting PID gains from the ultimate gain and period.", [("ultimate_gain", "Ultimate gain Ku", 8), ("ultimate_period_s", "Oscillation period Tu (s)", 0.5)], zn)


# ------------------------------------------------------------------ PCB and reliability
def trace(a):
    i, dt, oz, L = num(a, "current_a", lo=0, strict=True), num(a, "temp_rise_c", lo=1), num(a, "copper_oz", lo=0.25), num(a, "length_mm", lo=0)
    layer = txt(a, "layer").lower()
    k = {"external": 0.048, "internal": 0.024}.get(layer)
    if not k:
        raise ProError("Layer must be external or internal.")
    area = (i / (k * dt ** 0.44)) ** (1 / 0.725)
    t_mil = 1.378 * oz
    w = area / t_mil
    res = 1.72e-8 * (L / 1000) / ((w * 0.0254e-3) * (t_mil * 0.0254e-3))
    return {"width_mil": r(w, 1), "width_mm": r(w * 0.0254, 3), "resistance_mohm": r(res * 1000, 2), "voltage_drop_mv": r(res * i * 1000, 2),
            "tips": ["IPC-2221 is conservative for thin traces and rough above 35 A or very wide traces.", "Internal layers carry less current because heat cannot escape.", "Make traces wider where you can: lower resistance and drop, cooler board.", "Add vias in parallel to carry current between layers (about 1 A each for a standard via, check your fab)."]}


tool(T, "pcb_trace", "PCB trace width (IPC-2221)", "Width for a current and temperature rise.", [("current_a", "Current (A)", 2), ("temp_rise_c", "Allowed temperature rise (C)", 10), ("copper_oz", "Copper weight (oz)", 1), ("length_mm", "Trace length (mm)", 50), ("layer", "external or internal", "external")], trace)


def microstrip(a):
    w, h, t, er = num(a, "width_mm", lo=0, strict=True), num(a, "height_mm", lo=0, strict=True), num(a, "copper_mm", lo=0), num(a, "er", lo=1)
    z = 87 / math.sqrt(er + 1.41) * math.log(5.98 * h / (0.8 * w + t))
    ratio = w / h
    return {"impedance_ohm": r(z, 1), "width_to_height": r(ratio, 2), "valid": 0.1 <= ratio <= 2.0,
            "verdict": "Within the range the formula is good for (0.1 to 2.0)." if 0.1 <= ratio <= 2.0 else "Outside the formula's range: use your fab's impedance calculator.",
            "tips": ["Use the fab's stack-up numbers: dielectric height and constant vary by material.", "Keep a solid ground plane under high-speed traces and avoid splitting it.", "Match 50 ohm single-ended or 90 to 100 ohm differential for USB, Ethernet and similar."]}


tool(T, "microstrip_z", "Microstrip impedance", "Approximate impedance of a surface trace.", [("width_mm", "Trace width (mm)", 0.3), ("height_mm", "Dielectric height (mm)", 0.2), ("copper_mm", "Copper thickness (mm)", 0.035), ("er", "Dielectric constant", 4.3)], microstrip)


def reliability(a):
    rows = lines(a, "parts", "the parts")
    hours = num(a, "mission_hours", lo=0, strict=True)
    tot, parts = 0.0, []
    for p in rows:
        if len(p) < 2:
            raise ProError("Each line needs: part name, failures in time (FIT).")
        f = float(p[1])
        tot += f
        parts.append({"part": p[0], "fit": f})
    lam = tot / 1e9
    mtbf = 1 / lam if lam else None
    rel = math.exp(-lam * hours)
    big = max(parts, key=lambda x: x["fit"])
    return {"total_fit": r(tot, 1), "mtbf_hours": r(mtbf, 0) if mtbf else None, "mtbf_years": r(mtbf / 8766, 1) if mtbf else None, "reliability_over_mission": r(rel, 5), "with_one_redundant_copy": r(1 - (1 - rel) ** 2, 5), "biggest_contributor": big["part"],
            "parts": [{"part": x["part"], "share_pct": r(100 * x["fit"] / tot, 1)} for x in sorted(parts, key=lambda x: -x["fit"])] if tot else parts,
            "how": "Parts in series: failure rates add (FIT = failures per billion hours). MTBF = 1 / rate. Reliability over a mission = e^(-rate x hours). Assumes a constant failure rate (the flat part of the bathtub curve).", "tips": ["Attack the biggest contributor first.", "Run parts below their ratings (derating) to cut failure rate sharply.", "MTBF is not a lifetime: it is the average between failures across many units."]}


tool(T, "reliability", "Reliability and MTBF", "System failure rate from part failure rates.", [("parts", "Lines of: part, FIT", "MCU,20\nRegulator,15\nElectrolytic capacitor,60\nConnector,10", "area"), ("mission_hours", "Mission length (hours)", 8766)], reliability)


def derate(a):
    rated, actual, d = num(a, "rated", lo=0, strict=True), num(a, "actual", lo=0), num(a, "derating_pct", lo=1, hi=100)
    limit = rated * d / 100
    return {"stress_pct_of_rating": r(100 * actual / rated, 1), "allowed_at_derating": r(limit, 4), "ok": actual <= limit, "verdict": "Within the derating target." if actual <= limit else "Over the derating target: choose a higher-rated part or lower the stress.",
            "typical_targets": ["Resistors: 50% of rated power", "Ceramic and film capacitors: 50 to 70% of rated voltage", "Electrolytic capacitors: 80% of rated voltage", "Semiconductors: 70 to 80% of rated current, junction temperature 20 C under maximum"]}


tool(T, "derating", "Derating check", "Is a part run safely under its rating?", [("rated", "Rated value (V, A or W)", 0.25), ("actual", "Actual value", 0.15), ("derating_pct", "Allowed % of rating", 50)], derate)

# ------------------------------------------------------------------ reference tabs


# ------------------------------------------------------------------ real code checks (compile and simulate)
def verilog_tool(a):
    from app.services import codecheck
    try:
        return codecheck.verilog_sim(txt(a, "source", "the Verilog source", limit=60000), str(a.get("top", "")).strip())
    except codecheck.CodeError as e:
        raise ProError(e.message, e.status) from None


def c_tool(a):
    from app.services import codecheck
    try:
        return codecheck.c_check(txt(a, "source", "the C source", limit=60000), str(a.get("stdin", "")), str(a.get("run", "no")).strip().lower() in ("yes", "y", "true", "1", "run"))
    except codecheck.CodeError as e:
        raise ProError(e.message, e.status) from None


_V_DEMO = """module adder(input [3:0] a, b, output [4:0] s);
  assign s = a + b;
endmodule

module tb;
  reg [3:0] a, b; wire [4:0] s;
  adder u(.a(a), .b(b), .s(s));
  initial begin
    a = 3;  b = 4;  #1; if (s !== 7)  $display("FAIL 3+4=%d", s);   else $display("PASS 3+4");
    a = 15; b = 15; #1; if (s !== 30) $display("FAIL 15+15=%d", s); else $display("PASS 15+15");
    $finish;
  end
endmodule
"""
_C_DEMO = """#include <stdio.h>

int main(void) {
    int a[3] = {1, 2, 3};
    int sum = 0;
    for (int i = 0; i < 3; i++) sum += a[i];
    printf("sum=%d\\n", sum);
    return 0;
}
"""
tool(T, "verilog_sim", "Verilog simulator (real)", "Compile your design with Icarus Verilog and run its testbench. Reports failing checks, endless clocks and unknown (x) values. Needs iverilog installed.",
     [("source", "Paste the design and its testbench", _V_DEMO, "area"), ("top", "Top module (blank = the testbench)", "")], verilog_tool)
tool(T, "c_check", "C compile, lint and run (real)", "Compile C with strict warnings and, if you choose, run it with memory and undefined-behavior checks. Needs gcc installed. Only run code you have read.",
     [("source", "Paste the C source", _C_DEMO, "area"), ("stdin", "Input to feed the program (optional)", "", "area"), ("run", "Run it too? yes or no", "no")], c_tool)

ref(T, "datasheet", "Reading a datasheet", [
    {"title": "Read in this order", "items": ["Front page: what it is, key features, package, and the typical application.", "Absolute maximum ratings: limits that damage the part. Never design to these.", "Recommended operating conditions and electrical characteristics: what you design to, with min, typical and max.", "Pin description and the application circuit: copy the reference design first.", "Timing diagrams and tables: setup, hold, rise, propagation, with the test conditions.", "Thermal data: junction-to-ambient and the power the package can dissipate.", "Layout guidelines and errata: the cause of most surprise problems."]},
    {"title": "What to check before you buy", "items": ["Operating voltage and I/O level match your system (3.3 V vs 5 V).", "Maximum current on each pin and on the whole chip.", "Temperature grade (commercial, industrial, automotive).", "Package you can solder or have assembled.", "Availability and a second source; lifecycle status (active, not recommended for new designs).", "Worst-case values, not typical: typical is not guaranteed."]}])
ref(T, "embedded", "Embedded C and RTOS", [
    {"title": "Interrupts", "items": ["Keep the handler short: set a flag or copy data and return.", "Mark variables shared with a handler volatile, and protect multi-byte updates (disable the interrupt briefly or use atomic operations).", "Do not call blocking, printing or allocating functions in a handler.", "Clear the interrupt flag, and know the priority and whether handlers can nest."]},
    {"title": "RTOS essentials", "items": ["Tasks have priorities; the highest ready task runs.", "Use queues or semaphores between tasks instead of shared globals.", "Priority inversion: a low task holds a lock a high task needs. Use priority inheritance mutexes.", "Size each task's stack with margin and watch the high-water mark.", "A watchdog timer resets the system if the software hangs: feed it only when the main work completes."]},
    {"title": "Buses compared", "head": ["Bus", "Wires", "Speed", "Notes"], "rows": [["UART", "2 (TX, RX)", "to about 1 Mbps", "Asynchronous, point to point, agree the baud rate"], ["SPI", "4 (SCLK, MOSI, MISO, CS per device)", "10 to 50 MHz and up", "Fast, full duplex, a chip-select line per device"], ["I2C", "2 (SDA, SCL), shared", "100 kHz to 1 MHz", "Many devices by address, needs pull-ups, slower"], ["CAN", "2 (differential)", "to 1 Mbps (CAN FD faster)", "Robust, used in vehicles and industry"]]}])
ref(T, "hdl", "HDL and FPGA flow", [
    {"title": "The flow", "items": ["1 Specify: inputs, outputs, clock, reset, timing target.", "2 Write RTL in Verilog or VHDL.", "3 Simulate with a testbench until it passes (waveforms, assertions).", "4 Synthesize: turn RTL into gates and look-up tables; read warnings.", "5 Place and route, then read the timing report (setup and hold slack).", "6 Generate the bitstream, program the board, and test with real signals and a logic analyzer."]},
    {"title": "Verilog habits", "items": ["Use non-blocking assignments (<=) for clocked logic and blocking (=) for combinational logic.", "Every combinational branch assigns every output, or you create a latch by mistake.", "Reset every state register to a known value.", "Cross a clock domain with a two-flop synchronizer (single bits) or a FIFO (buses).", "Keep one clock per module where you can; treat asynchronous inputs (buttons) as unsafe until synchronized and debounced."]}])
ref(T, "arch", "Advanced architecture", [
    {"title": "Pipeline hazards", "items": ["Structural: two instructions need the same unit. Fix by duplicating units.", "Data: an instruction needs a result not ready yet. Forwarding fixes most; a load-use stall remains.", "Control: a branch changes the next address. Prediction hides the delay; a wrong guess flushes the pipeline."]},
    {"title": "Going faster", "items": ["Branch predictors learn patterns (two-bit counters, history tables).", "Out-of-order execution runs ready instructions ahead of stalled ones, then retires in order.", "Superscalar designs issue several instructions per cycle.", "Caches and prefetching hide memory latency; virtual memory with a TLB gives each program its own address space.", "Security: speculation can leak data through timing (Spectre-class issues), which is why mitigations cost speed."]}])
ref(T, "bench", "Oscilloscope and logic analyzer", [
    {"title": "Oscilloscope", "items": ["Probe: use the 10x setting, compensate the probe on the test signal, and keep the ground lead short.", "Set volts per division so the signal fills most of the screen; set time per division to show a few cycles.", "Trigger on the edge you care about; use single-shot for rare events.", "Bandwidth should be at least 5 times the signal's fastest frequency.", "Measure power-supply ripple with a short spring ground, not the long clip lead."]},
    {"title": "Logic analyzer", "items": ["Sample at least 4 times faster than the fastest signal (10 times is better).", "Set the voltage threshold to match the logic level.", "Use the protocol decoders (I2C, SPI, UART) to read bytes, and trigger on an address or byte.", "Capture before and after the trigger to see what led up to a fault."]}])
ref(T, "standards", "Standards, EMC and firmware security", [
    {"title": "Before you sell hardware", "items": ["FCC Part 15 (US) and CE marking (EU): radiated and conducted emissions limits for electronics.", "Safety: UL or an equivalent lab listing for mains-powered products and lithium batteries.", "RoHS and REACH: restricted substances.", "Wireless modules: use a pre-certified module to avoid full radio certification.", "Pre-compliance testing early is cheap; a failed final test is not."]},
    {"title": "Firmware security basics", "items": ["Secure boot: the chip checks a signature on the firmware before running it.", "Signed, encrypted updates with rollback protection.", "Disable debug ports (JTAG, SWD) or lock them in production.", "No hard-coded passwords or keys; give each device its own credentials.", "Keep a software bill of materials and a way to patch."]}])
ref(T, "kicad", "PCB design flow", [
    {"title": "KiCad-style flow", "items": ["1 Schematic: use library symbols, set footprints, run the electrical rules check.", "2 Board setup: layer count, stack-up, design rules from your fab (trace, space, drill).", "3 Placement: connectors and mechanical first, then critical parts close to their pins, decoupling capacitors next to power pins.", "4 Routing: power and ground first, then critical and high-speed nets; keep return paths short.", "5 Checks: design rules check, 3D view, review the gerbers in a viewer.", "6 Output gerbers, drill and the pick-and-place and bill of materials files."]},
    {"title": "Layout rules of thumb", "items": ["Solid ground plane on one layer; avoid splitting it under fast signals.", "Decoupling capacitor (100 nF) within a few millimetres of each power pin.", "Keep switching loops (inductor, switch, diode) small.", "Route differential pairs together with equal length and no stubs.", "Leave test points for power rails and key signals."]}])
