# -*- coding: utf-8 -*-
"""
라이닝 단면검토 — 콘크리트구조기준(2012) 강도설계법(읍애터널 설계 구조계산서 §3.1.1 다. 와 같은 체계).

무근:  압축  Pu/(φ·0.60·fck·[1-(lc/32h)²]·A1) + Mu/(φ·0.85·fck·S) ≤ 1   (φ, lc 는 lining.json "check.plain")
       인장  Mu/S − Pu/Ag ≤ 0.42·φ·λ·√fck
       전단  Vu ≤ φ·0.11·λ·√fck·b·h
철근:  복철근 As=As'(lining.json "check.rc": fy, Es, As, dc, bar, n_mod, s_bar)
       P-M: 편심 e=M/P 고정 선상 공칭강도, φ=0.65(압축지배)~0.85, φPn ≤ 0.80·0.65·Pn0
       전단 φVc = 0.75·(1/6)(1+Nu/14Ag)·λ·√fck·b·d
       균열(사용): s ≤ min(375(210/fs)−2.5Cc, 300(210/fs))
역검산(읍애 설계값): 무근 아치 0.554 / −1.125 MPa / φVn 94.31, RC φPn 4324.5 — `python -m lining selftest`.
등급: 세부지침(안전점검·진단, 터널편) [표 2.18] — SF = 설계강도/소요강도.
"""
import math
from . import post as LP

# 기본값 = 읍애터널(설계서 값). configure(prj) 가 lining.json 으로 바꾼다.
FY, ES, ECU = 400.0, 200000.0, 0.003
AS = 2292.0
DC = 60.0
CC_CLR = 60.0 - 19.0 / 2
N_MOD = 7
S_BAR = 125.0
LAM = 1.0
PHI_PLAIN, LC = 0.55, 0.5
RC_SECT = set()
STRENGTH = {"C1", "C2", "C3", "C4", "C2N"}
SERVICE = {"C5", "C6", "C7"}


def configure(prj):
    global FY, ES, AS, DC, CC_CLR, N_MOD, S_BAR, LAM, PHI_PLAIN, LC, RC_SECT, STRENGTH, SERVICE
    ck = prj.check
    rc = ck.get("rc", {})
    FY = rc.get("fy", FY); ES = rc.get("Es", ES); AS = rc.get("As", AS); DC = rc.get("dc", DC)
    CC_CLR = DC - rc.get("bar", 19.0) / 2; N_MOD = rc.get("n_mod", N_MOD); S_BAR = rc.get("s_bar", S_BAR)
    pl = ck.get("plain", {})
    PHI_PLAIN = pl.get("phi", PHI_PLAIN); LC = pl.get("lc", LC); LAM = ck.get("lambda", LAM)
    RC_SECT = prj.rc_patterns()
    STRENGTH = set(ck.get("strength_cases", STRENGTH)); SERVICE = set(ck.get("service_cases", SERVICE))


def plain(N, M, V, h, fck, phi=None, lc=None):
    phi = PHI_PLAIN if phi is None else phi; lc = LC if lc is None else lc
    A = h * 1.0; S = h * h / 6.0; fk = fck * 1000.0
    Pn = 0.60 * fk * (1 - (lc / (32 * h)) ** 2) * A
    Mn = 0.85 * fk * S
    comp = N / (phi * Pn) + abs(M) / (phi * Mn)
    ft = (abs(M) / S - N / A) / 1000.0
    ft_a = 0.42 * phi * LAM * math.sqrt(fck)
    Vn = phi * 0.11 * LAM * math.sqrt(fck) * 1000.0 * h
    return {"comp": comp, "ft": ft, "ft_a": ft_a, "ten": ft / ft_a, "phiVn": Vn, "shear": abs(V) / Vn}


def _beta1(fck):
    return 0.85 if fck <= 28 else max(0.65, 0.85 - 0.007 * (fck - 28))


def _state(c, h, fck, b=1000.0):
    b1 = _beta1(fck); a = min(b1 * c, h)
    Cc = 0.85 * fck * a * b
    F, M = Cc, Cc * (h / 2 - a / 2)
    d = h - DC; eps_t = None
    for y in (DC, d):
        eps = ECU * (c - y) / c
        fs = max(-FY, min(FY, ES * eps))
        if y <= a:
            fs -= 0.85 * fck
        Fs = AS * fs; F += Fs; M += Fs * (h / 2 - y)
        if y == d:
            eps_t = -eps
    return F, M, eps_t


def _phi(eps_t):
    ey = FY / ES
    if eps_t <= ey: return 0.65
    if eps_t >= 0.005: return 0.85
    return 0.65 + (eps_t - ey) * 0.20 / (0.005 - ey)


def rc_pm(N, M, h_m, fck):
    h = h_m * 1000.0; Pu = N * 1000.0; Mu = abs(M) * 1e6; Ag = h * 1000.0
    Pn0 = 0.85 * fck * (Ag - 2 * AS) + FY * 2 * AS
    phiPmax = 0.80 * 0.65 * Pn0
    if Pu <= 0:
        raise ValueError("축인장 — 별도 검토")
    e = Mu / Pu
    lo, hi = 1.0, 50.0 * h
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        P, Mm, _ = _state(mid, h, fck)
        em = Mm / P if P > 0 else 1e12
        if em > e: lo = mid
        else: hi = mid
    c = 0.5 * (lo + hi)
    P, Mm, et = _state(c, h, fck); ph = _phi(et)
    phiPn = min(ph * P, phiPmax)
    return {"ratio": Pu / phiPn, "phiPn": phiPn / 1000, "phiMn": phiPn / 1000 * e / 1000, "c": c, "phi": ph, "e_mm": e, "capped": ph * P > phiPmax}


def rc_shear(N, V, h_m, fck):
    d = h_m * 1000 - DC; Ag = h_m * 1e6; Nu = max(N, 0) * 1000
    phiVc = 0.75 * (1 / 6) * (1 + Nu / (14 * Ag)) * LAM * math.sqrt(fck) * 1000 * d / 1000
    return {"phiVc": phiVc, "shear": abs(V) / phiVc}


def rc_crack(N, M, h_m, fck):
    h = h_m * 1000; b = 1000.0; d = h - DC; dp = DC
    Nn = N * 1000; Mm = abs(M) * 1e6
    fr = 0.63 * math.sqrt(fck)
    sig_t = Mm / (b * h * h / 6) - Nn / (b * h)
    if sig_t <= fr:
        return {"cracked": False, "sig_t": sig_t, "fs": 0.0, "s_allow": None, "ok": True}
    n = N_MOD

    def forces(x):
        Cc = 0.5 * b * x; Fp = n * AS * (x - dp) / x; Ft = n * AS * (d - x) / x
        return Cc + Fp - Ft, Cc * (h / 2 - x / 3) + Fp * (h / 2 - dp) + Ft * (d - h / 2)
    e = Mm / Nn if Nn > 0 else 1e12
    lo, hi = 1.0, h
    for _ in range(200):
        x = 0.5 * (lo + hi)
        Nx, Mx = forces(x)
        ex = Mx / Nx if Nx > 0 else 1e12
        if ex > e: lo = x
        else: hi = x
    x = 0.5 * (lo + hi)
    Nx, _ = forces(x)
    smax = Nn / Nx; fs = n * smax * (d - x) / x
    s_allow = min(375 * (210 / fs) - 2.5 * CC_CLR, 300 * (210 / fs)) if fs > 0 else 1e9
    return {"cracked": True, "sig_t": sig_t, "x": x, "fs": fs, "s_allow": s_allow, "ok": s_allow >= S_BAR}


def rc_crack_M(M, h_m, n=None):
    """설계 구조계산서 방식: 축력 무시, 복철근 균열단면(압축철근 2n-1) → fs, 허용간격 (안전측)."""
    n = N_MOD if n is None else n
    h = h_m * 1000; b = 1000.0; d = h - DC; dp = DC; Mm = abs(M) * 1e6
    A_ = b / 2; B_ = (2 * n - 1) * AS + n * AS; C_ = -((2 * n - 1) * AS * dp + n * AS * d)
    x = (-B_ + math.sqrt(B_ * B_ - 4 * A_ * C_)) / (2 * A_)
    Icr = b * x ** 3 / 3 + n * AS * (d - x) ** 2 + (2 * n - 1) * AS * (x - dp) ** 2
    fs = n * Mm * (d - x) / Icr
    s_allow = min(375 * (210 / fs) - 2.5 * CC_CLR, 300 * (210 / fs)) if fs > 0 else 1e9
    return {"x": x, "Icr": Icr, "fs": fs, "s_allow": s_allow, "ok": s_allow >= S_BAR}


def sf_grade(ratio, damaged=None):
    sf = 1.0 / ratio if ratio > 0 else float("inf")
    if sf >= 1.0: g = "B" if damaged else ("A" if damaged is False else "A/B")
    elif sf >= 0.90: g = "C"
    elif sf >= 0.75: g = "D"
    else: g = "E"
    return sf, g


def check_run(prj, tag, fcks=None):
    fcks = fcks or (prj.fck,)
    R = LP.load(prj.result_path(tag))
    sec = R["sec"]; rc = sec in RC_SECT
    E = {e["id"]: e for e in R["geom"]["elems"]}
    out = {"tag": tag, "sec": sec, "type": "RC" if rc else "무근", "cases": {}}
    for lc, f in R["combos"]:
        F = R["F"][lc]; rows = []
        for eid, d in F.items():
            h = E[eid]["t_model"]; Vmid = 0.5 * (d["I"][1] + d["J"][1])
            for part, (Nax, V, M) in d.items():
                N = -Nax
                r = {"elem": eid, "part": part, "reg": E[eid]["reg"], "h": h, "N": N, "M": M, "V": V, "Vmid": Vmid}
                for fck in fcks:
                    k = "%g" % fck
                    if lc in STRENGTH:
                        if rc:
                            pm = rc_pm(N, M, h, fck); sh = rc_shear(N, V, h, fck); shm = rc_shear(N, Vmid, h, fck)
                            r[k] = {"pm": pm["ratio"], "phiPn": pm["phiPn"], "phiMn": pm["phiMn"], "phi": pm["phi"],
                                    "shear": sh["shear"], "shear_mid": shm["shear"], "phiVc": sh["phiVc"]}
                        else:
                            p = plain(N, M, V, h, fck); pmid = plain(N, M, Vmid, h, fck)
                            r[k] = {"comp": p["comp"], "ten": p["ten"], "ft": p["ft"], "ft_a": p["ft_a"],
                                    "shear": p["shear"], "shear_mid": pmid["shear"], "phiVn": p["phiVn"]}
                    elif lc in SERVICE and rc:
                        r[k] = {"crack": rc_crack(N, M, h, fck)}
                rows.append(r)
        out["cases"][lc] = {"f": f, "rows": rows}
    return out


def selftest(prj=None):
    """설계 구조계산서 값 역검산(lining.json "selftest" 가 있으면 그 값으로)"""
    st = (prj.cfg.get("selftest") if prj else None) or {
        "plain": [1006.0, 33.42, 57.88, 0.30, 27.0, "무근 아치 P-4 C2: 압축 0.554, 인장 -1.125/1.200, φVn 94.310"],
        "rc_pm": [2228.73, 72.86, 0.30, 27.0, "RC 아치 P-5 C2: φPn 4324.500, c 287.75"],
        "rc_shear": [2228.73, 127.12, 0.30, 27.0, "RC 전단 φVc 238.605"]}
    p = plain(*st["plain"][:5]); print("[역검산] 압축 %.3f 인장 %.3f MPa φVn %.2f  | 설계 %s" % (p["comp"], p["ft"], p["phiVn"], st["plain"][5]))
    q = rc_pm(*st["rc_pm"][:4]); print("[역검산] φPn %.1f c %.1f φ %.2f  | 설계 %s" % (q["phiPn"], q["c"], q["phi"], st["rc_pm"][4]))
    s = rc_shear(*st["rc_shear"][:4]); print("[역검산] φVc %.3f  | 설계 %s" % (s["phiVc"], st["rc_shear"][4]))
