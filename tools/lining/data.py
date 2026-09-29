# -*- coding: utf-8 -*-
"""
보고서용 수치 집계 → <프로젝트>/runs/report_data.json

lining.json "report": {"main": [주 해석 태그], "pin": [설계 조건(힌지) 태그], "bc": [경계조건·민감도 태그]}
하중조합 역할은 lining.json "combos" 의 세 번째 값("strength"/"service"/"aux") — 강도조합에서 지배값, 사용조합에서 균열 검토.
"""
import os, json
from . import post as LP
from . import check as C


def forces(R, lc):
    F = R["F"][lc]
    allc = [(e, p, -d[p][0], d[p][1], d[p][2]) for e, d in F.items() for p in d]   # N 압축+
    A = [c for c in allc if LP.region(R, c[0]) == "A"]
    W = [c for c in allc if LP.region(R, c[0]) != "A"]
    mp = max(A, key=lambda c: c[4]); mn = min(A, key=lambda c: c[4]); wm = max(W, key=lambda c: abs(c[4]))
    va = max(A, key=lambda c: abs(c[3])); vw = max(W, key=lambda c: abs(c[3]))
    pm = max(allc, key=lambda c: c[2])
    row = lambda c: {"elem": c[0], "N": round(c[2], 1), "M": round(c[4], 2), "V": round(c[3], 1)}
    return {"crown": row(mp), "shoulder": row(mn), "wall": row(wm), "Varch": row(va), "Vwall": row(vw), "Pmax": row(pm)}


def reactions(R, strength):
    """라이닝 끝절점(1, nn) 지점반력 — 힌지면 지점반력, 단부 스프링이면 0 이어야 한다."""
    nn = len(R["geom"]["nodes"])
    out = {}
    for r in R["REACTIONG"]["DATA"]:
        if r[2] in strength and int(r[1]) in (1, nn):
            k = "L" if int(r[1]) == 1 else "R"
            fx, fz = float(r[3]), float(r[5])
            o = out.setdefault(k, {"FX": 0.0, "FZ": 0.0})
            if abs(fx) > abs(o["FX"]): o["FX"] = fx
            if abs(fz) > abs(o["FZ"]): o["FZ"] = fz
    return out


def section(prj, tag):
    R = LP.load(prj.result_path(tag))
    sec = R["sec"]; fk = "%g" % prj.fck
    STRENGTH, SERVICE = prj.roles(sec, "strength"), prj.roles(sec, "service")
    res = C.check_run(prj, tag, fcks=(prj.fck,))
    E = {e["id"]: e for e in R["geom"]["elems"]}
    S = {"tag": tag, "sec": sec, "sup": R.get("sup"), "pv_mode": R.get("pv_mode"), "k_foot": R.get("k_foot"),
         "foot_b": R.get("foot_b"), "foot_alpha": R.get("foot_alpha"), "Ks": R["S"]["Ks"], "PV": R["S"]["PV"], "Pw": R["S"]["Pw"],
         "E0": R["S"].get("E0"), "ah": R.get("ah", 1.0),
         "combos": [(lc, f) for lc, f in R["combos"]], "forces": {}, "checks": {}, "disp": {}}
    nn = len(R["geom"]["nodes"])
    for lc, f in R["combos"]:
        S["forces"][lc] = forces(R, lc)
        D = {k: v for k, v in R["DP"][lc].items() if int(k) <= nn}
        z = min(D.items(), key=lambda kv: kv[1][1]); x = max(D.items(), key=lambda kv: abs(kv[1][0]))
        S["disp"][lc] = {"crown_mm": round(z[1][1] * 1000, 2), "crown_node": z[0], "x_mm": round(x[1][0] * 1000, 2), "x_node": x[0]}
    rows = [(lc, r) for lc, cz in res["cases"].items() if lc in STRENGTH for r in cz["rows"]]
    gov = {}
    keys = ("comp", "ten", "shear") if res["type"] == "무근" else ("pm", "shear")
    for grp, regs in (("아치", ("A",)), ("측벽", ("L", "R"))):
        for k in keys:
            cand = [(lc, r) for lc, r in rows if r["reg"] in regs]
            lc, r = max(cand, key=lambda t: t[1][fk][k])
            d = dict(r[fk]); d.update({"lc": lc, "elem": r["elem"], "part": r["part"], "h": r["h"], "N": round(r["N"], 1),
                                       "M": round(r["M"], 2), "V": round(r["V"], 1), "Vmid": round(r["Vmid"], 1)})
            d["SF"] = 1.0 / d[k] if d[k] > 0 else None
            gov["%s|%s" % (grp, k)] = d
    S["checks"] = gov
    if res["type"] == "무근":
        ft = [(lc, r) for lc, cz in res["cases"].items() for r in cz["rows"]]
        lc, r = max(ft, key=lambda t: t[1][fk]["ft"])
        S["ft_max"] = {"lc": lc, "elem": r["elem"], "ft": r[fk]["ft"]}
        lc2, r2 = max([(lc, r) for lc, r in ft if lc != "C1"], key=lambda t: t[1][fk]["ft"])
        S["ft_max_noC1"] = {"lc": lc2, "elem": r2["elem"], "ft": r2[fk]["ft"]}
    if res["type"] == "RC":
        crk = []
        for lc, cz in res["cases"].items():
            if lc not in SERVICE: continue
            for r in cz["rows"]:
                crk.append({"lc": lc, "elem": r["elem"], "reg": r["reg"], "h": r["h"], "N": r["N"], "M": r["M"], **r[fk]["crack"]})
        worst = {}
        for grp, regs in (("아치", ("A",)), ("측벽", ("L", "R"))):
            cand = [c for c in crk if c["reg"] in regs]
            for c_ in cand:
                m = C.rc_crack_M(c_["M"], c_["h"])
                c_.update({"fs_M": m["fs"], "s_allow_M": m["s_allow"], "ok_M": m["ok"], "x_M": m["x"]})
                c_["ft_N"] = abs(c_["M"]) * 1e6 / (1000 * (c_["h"] * 1000) ** 2 / 6) - c_["N"] * 1e3 / (1000 * c_["h"] * 1000)
            worst[grp] = max(cand, key=lambda c: c["fs_M"])
            worst[grp + "_ftN"] = max(c["ft_N"] for c in cand)
        S["crack"] = worst
    sfs = {k: v["SF"] for k, v in gov.items() if v["SF"] and not k.endswith("ten")}
    kmin = min(sfs, key=sfs.get)
    S["SF_min"] = sfs[kmin]; S["SF_min_at"] = kmin; S["SF_min_lc"] = gov[kmin]["lc"]; S["SF_min_elem"] = gov[kmin]["elem"]
    S["grade"] = C.sf_grade(1 / S["SF_min"])[1]
    S["type"] = res["type"]
    S["reac"] = reactions(R, STRENGTH)
    S["geom_t"] = {"arch": 0.300,
                   "L": [min(E[i]["t"] for i in E if E[i]["reg"] == "L"), max(E[i]["t"] for i in E if E[i]["reg"] == "L")],
                   "R": [min(E[i]["t"] for i in E if E[i]["reg"] == "R"), max(E[i]["t"] for i in E if E[i]["reg"] == "R")]}
    S["geom_t"]["arch"] = prj.cfg.get("report", {}).get("arch_t", 0.300)
    st = STRENGTH
    S["env"] = {"arch_M": max(S["forces"][lc]["crown"]["M"] for lc in st),
                "wall_M": max(abs(S["forces"][lc]["wall"]["M"]) for lc in st),
                "wall_V": max(abs(S["forces"][lc]["Vwall"]["V"]) for lc in st),
                "arch_V": max(abs(S["forces"][lc]["Varch"]["V"]) for lc in st),
                "crown_mm": min(S["disp"][lc]["crown_mm"] for lc in st)}
    return S


def build(prj, out_path=None, quiet=False):
    C.configure(prj)
    rep = prj.cfg["report"]
    MAIN, PIN, BC = rep.get("main", []), rep.get("pin", []), rep.get("bc", [])
    out = {"sections": {}}
    for tag in dict.fromkeys(MAIN + PIN + BC):
        out["sections"][tag] = section(prj, tag)
    out["main"] = list(MAIN); out["pin"] = list(PIN); out["bc"] = list(BC)
    out_path = out_path or os.path.join(prj.runs, "report_data.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    if not quiet:
        for tag, S in out["sections"].items():
            e = S["env"]
            print("== %-13s %s %-4s SF_min %.2f (%s, %s, 부재 %s) %s | 아치M %.1f 측벽M %.1f 측벽V %.1f 천단 %.1f mm" % (
                tag, S["sec"], S["type"], S["SF_min"], S["SF_min_at"], S["SF_min_lc"], S["SF_min_elem"], S["grade"],
                e["arch_M"], e["wall_M"], e["wall_V"], e["crown_mm"]))
    return out
