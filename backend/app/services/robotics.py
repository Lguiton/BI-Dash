"""Robotics lab: sizing and simulation helpers, sensor and driver reference, wiring and safety checklists, and starter projects.
Reference and planning only. Real robots need testing with the motor and battery in hand: use these numbers to choose parts, then verify on the bench."""
from __future__ import annotations

import math

NOTE = "Planning estimates with simple physics. Real motors, friction and batteries differ. Always test on the bench with the robot lifted off the ground first."
G = 9.81


class RoboError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _n(v, name, lo=0.0, hi=1e9, strict=True) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise RoboError(f"{name} must be a number.") from None
    if (x <= lo if strict else x < lo) or x > hi:
        raise RoboError(f"{name} must be {'more than' if strict else 'at least'} {lo:g} and at most {hi:g}.")
    return x


def drive_motor(mass_kg, wheel_mm, speed_ms, accel_ms2=0.5, incline_deg=0, wheels=2, rolling=0.03, efficiency=0.7, safety=2.0) -> dict:
    m, d, v = _n(mass_kg, "Mass (kg)", 0, 500), _n(wheel_mm, "Wheel diameter (mm)", 0, 1000), _n(speed_ms, "Top speed (m/s)", 0, 30)
    a, th = _n(accel_ms2, "Acceleration (m/s2)", 0, 20, False), _n(incline_deg, "Incline (degrees)", -30, 45, False)
    n, crr, eff, sf = int(_n(wheels, "Driven wheels", 0, 12)), _n(rolling, "Rolling resistance", 0, 0.5, False), _n(efficiency, "Efficiency (0 to 1)", 0, 1), _n(safety, "Safety factor", 0.99, 10)
    r = d / 2000
    t = math.radians(th)
    force = m * (G * math.sin(t) + G * crr * math.cos(t) + a)
    torque_total = force * r
    per = torque_total / n
    rpm = v / (math.pi * d / 1000) * 60
    mech = max(force, 0) * v
    return {"force_n": round(force, 2), "torque_per_wheel_nm": round(per, 3), "torque_per_wheel_kgcm": round(per * 10.197, 2), "wheel_rpm": round(rpm, 1),
            "mechanical_power_w": round(mech, 1), "electrical_power_w": round(mech / eff, 1),
            "choose_motor_torque_nm": round(per * sf, 3), "choose_motor_kgcm": round(per * sf * 10.197, 2),
            "advice": ["Pick a motor and gearbox whose continuous torque at the wheel is at least the 'choose' value, at about the wheel rpm shown.", "If the motor's free speed is higher than needed, add a gear reduction: torque goes up by the ratio and speed goes down by it.",
                       "Check the motor driver handles the motor's stall current, not just its running current.", "Stall torque is not usable torque: do not size to stall."], "note": NOTE}


def gearbox(motor_rpm, motor_torque_nm, ratio, efficiency=0.85) -> dict:
    rpm, tq, r, e = _n(motor_rpm, "Motor rpm", 0, 100000), _n(motor_torque_nm, "Motor torque (N m)", 0, 1000), _n(ratio, "Gear ratio (n:1)", 0, 10000), _n(efficiency, "Efficiency", 0, 1)
    return {"output_rpm": round(rpm / r, 2), "output_torque_nm": round(tq * r * e, 3), "output_torque_kgcm": round(tq * r * e * 10.197, 2), "note": "Ratio n:1 means the motor turns n times for one output turn. Efficiency drops with more stages."}


def battery(capacity_mah, voltage, avg_current_a, c_rating=20, peak_current_a=None, usable=0.8) -> dict:
    cap, v, i, c = _n(capacity_mah, "Capacity (mAh)", 0, 1e6), _n(voltage, "Voltage (V)", 0, 100), _n(avg_current_a, "Average current (A)", 0, 1000), _n(c_rating, "C rating", 0, 200)
    u = _n(usable, "Usable fraction", 0, 1)
    hours = cap / 1000 * u / i
    maxi = cap / 1000 * c
    out = {"runtime_minutes": round(hours * 60, 1), "energy_wh": round(cap / 1000 * v, 1), "max_continuous_a": round(maxi, 1), "usable_fraction": u,
           "tips": ["Plan on 70 to 80% usable capacity to protect the cells.", "Add a low-voltage cutoff and use the right charger for the chemistry.", "LiPo and Li-ion packs need a protection board or monitor and a fireproof charging spot; never charge unattended."]}
    if peak_current_a is not None and str(peak_current_a) != "":
        p = _n(peak_current_a, "Peak current (A)", 0, 5000)
        out["peak_ok"] = p <= maxi
        out["peak_note"] = "The pack can supply that peak." if p <= maxi else f"Peak {p:g} A is above this pack's {maxi:.1f} A rating. Use a higher C rating or more capacity."
    return {**out, "note": NOTE}


def servo(arm_cm, load_kg, arm_mass_kg=0.0, safety=2.0) -> dict:
    L, w, am, sf = _n(arm_cm, "Arm length (cm)", 0, 300), _n(load_kg, "Load (kg)", 0, 100, False), _n(arm_mass_kg, "Arm mass (kg)", 0, 50, False), _n(safety, "Safety factor", 0.99, 10)
    need = (w * L + am * L / 2)
    return {"torque_needed_kgcm": round(need, 2), "choose_servo_kgcm": round(need * sf, 2), "choose_servo_nm": round(need * sf / 10.197, 3),
            "tips": ["This is the worst case with the arm horizontal. Hold torque at the rated voltage; hobby servos stall and overheat if pushed to their limit.", "Check the servo's stall current against your supply, and power servos from a separate regulated rail, not the logic pin.", "Metal gears survive shock loads better than plastic."], "note": NOTE}


def pid(kp, ki, kd, setpoint=1.0, tau=1.0, gain=1.0, dead_time=0.0, umax=10.0, seconds=10.0) -> dict:
    kp, ki, kd = _n(kp, "Kp", -1, 1000, False), _n(ki, "Ki", -1, 1000, False), _n(kd, "Kd", -1, 1000, False)
    sp, tau, K = _n(setpoint, "Setpoint", -1e6, 1e6, False), _n(tau, "Plant time constant (s)", 0, 100), _n(gain, "Plant gain", 0, 1000)
    dt_, um, T = _n(dead_time, "Dead time (s)", -1, 10, False), _n(umax, "Output limit", 0, 1e6), _n(seconds, "Seconds", 0, 60)
    dt = 0.005
    steps = int(T / dt)
    delay = int(dt_ / dt)
    ubuf = [0.0] * (delay + 1)
    y, integ, prev_e = 0.0, 0.0, sp
    ys, ts = [], []
    for k in range(steps):
        e = sp - y
        d = (e - prev_e) / dt if k else 0.0
        u_unsat = kp * e + ki * integ + kd * d
        u = max(-um, min(um, u_unsat))
        if abs(u_unsat) < um or (u_unsat * e) < 0:      # anti-windup: only integrate when not saturated, or when it unwinds
            integ += e * dt
        prev_e = e
        ubuf.append(u)
        ud = ubuf.pop(0)
        y += dt * (-y + K * ud) / tau
        if k % max(1, steps // 80) == 0:
            ys.append(round(y, 4)); ts.append(round(k * dt, 3))
    final = y
    peak = max(ys) if sp >= 0 else min(ys)
    over = max(0.0, (peak - sp) / abs(sp) * 100) if sp else 0.0
    rise = settle = None
    if sp:
        lo, hi = 0.1 * sp, 0.9 * sp
        t10 = next((t for t, v in zip(ts, ys) if (v >= lo if sp > 0 else v <= lo)), None)
        t90 = next((t for t, v in zip(ts, ys) if (v >= hi if sp > 0 else v <= hi)), None)
        rise = round(t90 - t10, 3) if t10 is not None and t90 is not None else None
        out_idx = [i for i, v in enumerate(ys) if abs(v - sp) > 0.02 * abs(sp)]
        settle = round(ts[out_idx[-1] + 1], 3) if out_idx and out_idx[-1] + 1 < len(ts) else (None if out_idx else 0.0)
    unstable = any(abs(v) > 50 * max(1.0, abs(sp)) for v in ys)
    adv = []
    if unstable:
        adv.append("Unstable: the output grows. Lower Kp and Kd, and remove Ki until it settles.")
    if over > 20:
        adv.append("Large overshoot: lower Kp or Ki, or add some Kd.")
    if abs(final - sp) > 0.02 * max(abs(sp), 1e-9) and not unstable:
        adv.append("Steady-state error remains: add a little Ki, or give it more time.")
    if rise and rise > 3 * tau:
        adv.append("Slow response: raise Kp.")
    if not adv:
        adv.append("Looks reasonable for this model. Real systems have noise, backlash and delay: retune on the real robot.")
    return {"t": ts, "y": ys, "setpoint": sp, "final": round(final, 4), "overshoot_pct": round(over, 1), "rise_time_s": rise, "settling_time_s": settle, "unstable": unstable, "advice": adv,
            "tuning": ["Start with Ki and Kd at 0 and raise Kp until it responds quickly with a little overshoot.", "Add Kd to damp overshoot, then a small Ki to remove steady error.", "Limit the integral term (anti-windup) and the output.", "Filter the derivative if the sensor is noisy."], "note": "A simple first-order model with optional delay. It teaches the effect of each term; it is not your robot."}


def arm_fk(l1, l2, a1_deg, a2_deg) -> dict:
    a, b = _n(l1, "Link 1", 0, 1e4), _n(l2, "Link 2", 0, 1e4)
    t1, t2 = math.radians(_n(a1_deg, "Angle 1", -360, 360, False)), math.radians(_n(a2_deg, "Angle 2", -360, 360, False))
    x1, y1 = a * math.cos(t1), a * math.sin(t1)
    return {"elbow": [round(x1, 3), round(y1, 3)], "end": [round(x1 + b * math.cos(t1 + t2), 3), round(y1 + b * math.sin(t1 + t2), 3)], "reach_max": round(a + b, 3), "reach_min": round(abs(a - b), 3)}


def arm_ik(l1, l2, x, y) -> dict:
    a, b, px, py = _n(l1, "Link 1", 0, 1e4), _n(l2, "Link 2", 0, 1e4), _n(x, "x", -1e5, 1e5, False), _n(y, "y", -1e5, 1e5, False)
    d2 = px * px + py * py
    d = math.sqrt(d2)
    if d > a + b + 1e-9:
        raise RoboError(f"Out of reach: the target is {d:.2f} away and the arm reaches {a + b:.2f} at most.")
    if d < abs(a - b) - 1e-9:
        raise RoboError(f"Too close: the arm cannot fold in to {d:.2f}; the minimum is {abs(a - b):.2f}.")
    c2 = max(-1.0, min(1.0, (d2 - a * a - b * b) / (2 * a * b)))
    sols = []
    for sign, name in ((1, "elbow down"), (-1, "elbow up")):
        t2 = sign * math.acos(c2)
        t1 = math.atan2(py, px) - math.atan2(b * math.sin(t2), a + b * math.cos(t2))
        sols.append({"name": name, "angle1_deg": round(math.degrees(t1), 2), "angle2_deg": round(math.degrees(t2), 2)})
    return {"solutions": sols, "note": "Two arrangements reach the same point. Pick the one your joint limits and obstacles allow, and check for singularities at full stretch or folded."}


def diff_drive(v_left, v_right, wheelbase_m, seconds=5.0, dt=0.05) -> dict:
    vl, vr = _n(v_left, "Left wheel speed (m/s)", -50, 50, False), _n(v_right, "Right wheel speed (m/s)", -50, 50, False)
    L, T, h = _n(wheelbase_m, "Wheelbase (m)", 0, 10), _n(seconds, "Seconds", 0, 600), _n(dt, "Step (s)", 0.0009, 1)
    x = y = th = 0.0
    pts = [[0.0, 0.0]]
    for _ in range(int(T / h)):
        v, w = (vl + vr) / 2, (vr - vl) / L
        x += v * math.cos(th) * h
        y += v * math.sin(th) * h
        th += w * h
        pts.append([round(x, 3), round(y, 3)])
    step = max(1, len(pts) // 60)
    w = (vr - vl) / L
    return {"x": round(x, 3), "y": round(y, 3), "heading_deg": round(math.degrees(th) % 360, 1), "turn_radius_m": None if abs(w) < 1e-9 else round(abs((vl + vr) / 2 / w), 3),
            "path": pts[::step], "note": "Ideal odometry with no wheel slip. Real robots drift: use an IMU or other references to correct it."}


def encoder(counts_per_rev, wheel_mm, gear_ratio=1.0, quadrature=True) -> dict:
    c, d, g = _n(counts_per_rev, "Counts per revolution", 0, 1e6), _n(wheel_mm, "Wheel diameter (mm)", 0, 1000), _n(gear_ratio, "Gear ratio", 0, 10000)
    ticks = c * (4 if quadrature else 1) * g
    return {"ticks_per_wheel_rev": round(ticks, 1), "mm_per_tick": round(math.pi * d / ticks, 4), "note": "Counts are per motor-shaft turn before the gearbox. Quadrature decoding counts 4 edges per cycle."}


def ultrasonic(echo_us, temp_c=20.0) -> dict:
    t, tc = _n(echo_us, "Echo time (microseconds)", 0, 100000), _n(temp_c, "Temperature (C)", -40, 85, False)
    v = 331.3 + 0.606 * tc
    return {"distance_cm": round(t * v / 10000 / 2, 2), "speed_of_sound_ms": round(v, 1), "note": "Round-trip time is halved. Soft and angled surfaces can return no echo. Typical sensors read about 2 cm to 4 m."}


KINDS = {"drive": drive_motor, "gearbox": gearbox, "battery": battery, "servo": servo, "pid": pid, "arm_fk": arm_fk, "arm_ik": arm_ik, "diff_drive": diff_drive, "encoder": encoder, "ultrasonic": ultrasonic}


def calc(kind: str, args: dict) -> dict:
    if kind not in KINDS:
        raise RoboError("Unknown calculator. Use one of: " + ", ".join(KINDS) + ".")
    args = args or {}
    try:
        return KINDS[kind](**{k: v for k, v in args.items() if k in KINDS[kind].__code__.co_varnames[:KINDS[kind].__code__.co_argcount]})
    except TypeError as e:
        raise RoboError("Missing a number: " + str(e).split("argument")[-1].strip(" '")) from None


SENSORS = [
    {"name": "Ultrasonic (HC-SR04 style)", "use": "Distance 2 cm to about 4 m", "how": "Trigger pulse, then time the echo", "watch": "Wide beam, misses soft or angled surfaces, 5 V logic needs level shift for 3.3 V boards"},
    {"name": "IR distance (Sharp type)", "use": "Short range obstacle distance", "how": "Analog voltage vs distance", "watch": "Non-linear, affected by sunlight and surface color"},
    {"name": "Time-of-flight (VL53L0X/VL53L1X)", "use": "Precise short to medium distance", "how": "I2C", "watch": "Glass and sunlight; set the I2C address when using several"},
    {"name": "Lidar (2D spinning or solid state)", "use": "Mapping and obstacle avoidance", "how": "UART or USB, point cloud", "watch": "Power, eye safety class, processing load"},
    {"name": "IMU (accelerometer, gyro, magnetometer)", "use": "Orientation, balance, turn rate", "how": "I2C or SPI with sensor fusion", "watch": "Gyro drift, magnetometer interference from motors"},
    {"name": "Wheel encoder", "use": "Speed and distance", "how": "Quadrature A/B pulses on interrupt or hardware counter", "watch": "Debounce, wheel slip, max pulse rate vs your microcontroller"},
    {"name": "Line sensor (IR reflectance)", "use": "Line following", "how": "Analog or digital array", "watch": "Calibrate on the real surface and lighting"},
    {"name": "Camera", "use": "Vision, tags, line detection", "how": "USB, MIPI or I2C module with a single-board computer", "watch": "Latency, lighting, compute and power"},
    {"name": "Current sensor", "use": "Stall and load detection", "how": "Hall effect or shunt amplifier", "watch": "Sample fast enough to see stalls"},
    {"name": "Limit switch, bumper", "use": "Hard stops and safety", "how": "Digital input with pull-up", "watch": "Always provide a hardware stop for arms and linear axes"},
]

DRIVERS = [
    {"type": "Brushed DC motor driver (H-bridge)", "examples": "L298N (old, wasteful), TB6612, DRV8871, BTS7960", "for": "Wheels and simple motors", "tips": "Match voltage and stall current, add flyback protection if not built in, use PWM at 20 kHz or more for quiet motors"},
    {"type": "Stepper driver", "examples": "A4988, DRV8825, TMC2209", "for": "Precise positioning, 3D printer style axes", "tips": "Set current limit with the reference voltage, use microstepping, add a motor supply capacitor and never connect or disconnect the motor while powered"},
    {"type": "Servo (hobby PWM)", "examples": "SG90, MG996R and similar", "for": "Arms, grippers, steering", "tips": "50 Hz pulse of about 1 to 2 ms, separate 5 V rail with enough current, ground tied to the controller"},
    {"type": "Brushless (ESC or FOC driver)", "examples": "Drone ESCs, SimpleFOC boards, ODrive", "for": "High power and efficiency, gimbals, fast robots", "tips": "Needs sensor or sensorless tuning, observe current limits, and arm with a safe procedure"},
    {"type": "Smart serial servo", "examples": "Dynamixel, Feetech", "for": "Robot arms with feedback", "tips": "Daisy chain bus, set unique IDs, watch temperature and torque limit"},
]

WIRING = [
    "Share a common ground between the controller, drivers and sensors.", "Separate motor power from logic power or use a good regulator with bulk capacitors, so motor noise does not reset the controller.",
    "Put a master switch and a fuse (or breaker) near the battery, rated for the wire and the load.", "Use a physical emergency stop that cuts motor power, not just a software stop.",
    "Match wire gauge to current; keep high-current runs short, and strain-relieve connectors.", "Add flyback or TVS protection and decoupling capacitors near drivers.",
    "Use level shifters between 5 V and 3.3 V logic.", "Test the drive system with the wheels lifted off the ground first.", "Add a watchdog or timeout so the motors stop if the controller hangs or the radio link drops.",
    "Label polarity and test battery connection with a meter before powering the controller.",
]

SAFETY = [
    "Treat every robot as able to hurt: pinch points on gears, arms and wheels, flying parts, and fast motors.", "Lithium batteries (LiPo, Li-ion) can burn: use the correct charger, a protection circuit, a safe charging spot, never charge unattended and never use a swollen pack.",
    "Keep the robot lifted or the motors disconnected while you reflash firmware and when you are first testing.", "Test arms at low speed and torque with clear space around, and add limit switches and torque limits.",
    "Do not build or sell anything intended to harm people, and follow rules for drones, radios and batteries where it will operate.", "For anything that goes near people or runs on mains power, get a qualified review.",
]

PROJECTS = [
    {"id": "line-follower", "title": "Line-following car", "level": "Beginner", "parts": "Microcontroller (Arduino or similar), 2 gear motors with wheels, motor driver, 3 to 5 IR line sensors, battery pack, chassis",
     "steps": ["Wire and test each motor with wheels lifted.", "Read and print the sensor values over the line and the floor, then pick a threshold.", "Write bang-bang steering: turn toward the line.", "Upgrade to proportional control using the weighted position of the line.", "Tune speed and gains; add a stop when the line ends."], "learn": "Sensors, motor drivers, closed-loop control"},
    {"id": "obstacle", "title": "Obstacle-avoiding rover", "level": "Beginner", "parts": "Microcontroller, motors and driver, ultrasonic or time-of-flight sensor, servo for sweeping (optional), battery", "steps": ["Drive forward and stop at a set distance.", "Back up and turn a random amount, then continue.", "Sweep the sensor on a servo to pick the clearer side.", "Add a bumper switch as a last-resort stop."], "learn": "State machines, distance sensing"},
    {"id": "arm", "title": "Two-joint robot arm", "level": "Intermediate", "parts": "2 to 4 servos (or smart servos), a rigid frame, separate 5 to 6 V supply, microcontroller, limit switches", "steps": ["Calibrate each servo's zero and range and set software limits.", "Use the arm inverse kinematics tool to compute angles for a target.", "Move smoothly with speed ramps instead of jumping.", "Add a gripper and test with light objects.", "Add a stop and a torque/current check."], "learn": "Kinematics, torque, power"},
    {"id": "balance", "title": "Self-balancing robot", "level": "Advanced", "parts": "Microcontroller, IMU, two geared motors with encoders, motor driver, battery", "steps": ["Read the tilt angle with a complementary or Kalman filter.", "Close a fast PID loop (100 Hz or more) on tilt that drives the wheels.", "Tune Kp for response, Kd for damping, Ki sparingly.", "Add speed and position loops outside the balance loop."], "learn": "Sensor fusion, fast control loops, tuning"},
    {"id": "mobile-ros", "title": "Mapping robot with ROS 2", "level": "Advanced", "parts": "Single-board computer (Raspberry Pi class), 2D lidar, differential drive base with encoders, IMU, battery", "steps": ["Get the base driving with encoders and publish odometry.", "Add lidar and visualize scans.", "Run SLAM to build a map and save it.", "Use navigation to drive between points and avoid obstacles."], "learn": "ROS 2, SLAM, navigation, systems integration"},
]

CONCEPTS = [
    {"h": "Open loop vs closed loop", "p": "Open loop sends a command and hopes. Closed loop measures the result and corrects it. Almost every useful robot behavior is closed loop."},
    {"h": "Torque, speed and gearing", "p": "A gearbox trades speed for torque. Size the motor from the force needed at the wheel, then pick a ratio to hit the target speed."},
    {"h": "Power and batteries", "p": "Motors draw far more at start and stall than while running. The battery and wiring must handle the peak, and the controller must be protected from motor noise."},
    {"h": "Sensors and noise", "p": "Every sensor is noisy and slow in its own way. Filter, calibrate and combine sensors (sensor fusion) instead of trusting one reading."},
    {"h": "Kinematics", "p": "Forward kinematics turns joint angles into a position. Inverse kinematics finds the angles to reach a position, often with more than one answer."},
    {"h": "Control: PID", "p": "P reacts to the error now, I removes lingering error, D resists fast change. Tune in that order and protect against integral windup."},
    {"h": "State machines and software structure", "p": "Break behavior into states (search, approach, grab, return) with clear transitions, and keep fast control loops separate from slow decisions."},
    {"h": "Safety", "p": "Plan stops first: hardware emergency stop, timeouts, limits, and testing with wheels or arms secured."},
]


def reference() -> dict:
    return {"sensors": SENSORS, "drivers": DRIVERS, "wiring": WIRING, "safety": SAFETY, "projects": PROJECTS, "concepts": CONCEPTS, "kinds": list(KINDS), "note": NOTE}
