# -*- coding: utf-8 -*-
"""결과 JSON(<태그>_result.json) → 요소 단면력·반력·변위 정리, 압축전용 링크 점검, 설계 단면력 대조(lining.json "design_forces")."""
import json


def load(path):
    R = json.load(open(path, encoding="utf-8"))
    head = R["BEAMFORCE"]["HEAD"]; ix = {h: i for i, h in enumerate(head)}
    F = {}   # F[case][elem] = {"I": (N, V, M), "J": (...)}
    for row in R["BEAMFORCE"]["DATA"]:
        e = int(row[ix["Elem"]]); lc = row[ix["Load"]].replace("(ST)", "").strip()
        part = "I" if "I" in row[ix["Part"]] else "J"
        F.setdefault(lc, {}).setdefault(e, {})[part] = (float(row[ix["Axial"]]), float(row[ix["Shear-z"]]), float(row[ix["Moment-y"]]))
    R["F"] = F
    hr = R["REACTIONG"]["HEAD"]; ir = {h: i for i, h in enumerate(hr)}
    RX = {}
    for row in R["REACTIONG"]["DATA"]:
        nd = int(row[ir["Node"]]); lc = row[ir["Load"]].replace("(ST)", "").strip()
        RX.setdefault(lc, {})[nd] = (float(row[ir["FX"]]), float(row[ir["FZ"]]), float(row[ir["MY"]]))
    R["RX"] = RX
    hd = R["DISPLACEMENTG"]["HEAD"]; idd = {h: i for i, h in enumerate(hd)}
    DP = {}
    for row in R["DISPLACEMENTG"]["DATA"]:
        nd = int(row[idd["Node"]]); lc = row[idd["Load"]].replace("(ST)", "").strip()
        DP.setdefault(lc, {})[nd] = (float(row[idd["DX"]]), float(row[idd["DZ"]]))
    R["DP"] = DP
    return R


def region(R, eid):
    return R["geom"]["elems"][eid - 1]["reg"]


def summary(R, lc):
    """아치/측벽별 |M|max(+N), |V|max, |N|max(+M). 부재 양단 중 큰 값."""
    F = R["F"][lc]
    out = {}
    for grp, regs in (("arch", ("A",)), ("wall", ("L", "R"))):
        cand = [(e, p, *d[p]) for e, d in F.items() if region(R, e) in regs for p in d]
        m = max(cand, key=lambda c: abs(c[4])); v = max(cand, key=lambda c: abs(c[3])); pmax = max(cand, key=lambda c: -c[2])
        out[grp + "_M"] = (m[4], -m[2], m[0], m[1]); out[grp + "_V"] = (v[3], v[0], v[1]); out[grp + "_P"] = (pmax[4], -pmax[2], pmax[0], pmax[1])
    allc = [(e, p, *d[p]) for e, d in F.items() for p in d]
    out["M_pos"] = max(allc, key=lambda c: c[4]); out["M_neg"] = min(allc, key=lambda c: c[4]); out["N_crown"] = min(allc, key=lambda c: -c[2])
    return out


def link_check(R, lc, gnd0=100):
    nn = len(R["geom"]["nodes"])
    comp, inact, tens = 0, 0, []
    for i in range(1, nn + 1):
        fx, fz, _ = R["RX"][lc].get(gnd0 + i, (0, 0, 0))
        nx, nz = R["geom"]["normals"][i - 1]
        s = fx * nx + fz * nz            # 지반절점 반력의 외향성분: 압축이면 음
        if abs(s) < 1e-3: inact += 1
        elif s < 0: comp += 1
        else: tens.append((i, s))
    return comp, inact, tens


def report(prj, tag):
    R = load(prj.result_path(tag))
    DES = prj.cfg.get("design_forces", {}).get(R["sec"], {})
    print("=" * 78)
    print("%s  (PV %s)  Ks=%.0f  PV=%.3f  Pw=%.3f" % (R["tag"], R["pv_mode"], R["S"]["Ks"], R["S"]["PV"], R["S"]["Pw"]))
    for lc, f in R["combos"]:
        s = summary(R, lc)
        comp, inact, tens = link_check(R, lc, prj.gnd0)
        sumFz = sum(v[1] for v in R["RX"][lc].values())
        dz = min(R["DP"][lc].values(), key=lambda d: d[1])[1]
        print("\n[%s] %s   링크: 압축 %d / 비활성 %d / 인장 %d   ΣRz=%.1f kN   천단침하 %.2f mm" % (lc, f, comp, inact, len(tens), sumFz, dz * 1000))
        if tens: print("   !! 인장 링크:", tens[:5])
        D = DES.get(lc, {})
        for key, lab in (("arch_M", "아치 Mmax"), ("arch_V", "아치 Vmax"), ("wall_M", "측벽 Mmax"), ("wall_V", "측벽 Vmax")):
            print("   %-9s %s   | 설계 %s" % (lab, tuple(round(x, 2) if isinstance(x, float) else x for x in s[key]), D.get(key, "-")))
    return R
