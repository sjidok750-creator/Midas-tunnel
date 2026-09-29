# -*- coding: utf-8 -*-
"""
라이닝 빔-스프링 모델 — MIDAS CIVIL NX (Open API).  (실증 프로젝트 스크립트를 프로젝트 입력 방식으로 일반화)

- 형상: geom.build(prj) (표준단면도 원호)
- 지반: 절점별 법선방향 압축전용 탄성링크(COMP), k = Ks × 분담길이 × 1.0 m, 지반절점 link_len 외측 고정
- 끝점(sup): pin(111101) | roller | fix | spring(단부 스프링 — 끝점에서 라이닝 축선 방향으로 연장한 지반절점과 COMP 링크)
- 하중 분포 pv_mode/pw_mode: ncos(법선, P·cosθ, 스프링라인 아래 0 — 기본) | normal(법선 등분포) | vertical(수평투영 연직) | ncos2
- 하중조합마다 계수하중을 한 하중케이스로 해석한다(압축전용 링크 → 중첩 불가).
- ah: 강도조합(계수 ≠ 1.0)의 이완하중에만 곱하는 토피보정계수 αH
"""
import os, sys, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_TOOLS = os.path.normpath(os.path.join(HERE, "..", "..", "core", "tools"))
if CORE_TOOLS not in sys.path:
    sys.path.insert(0, CORE_TOOLS)

from . import geom as G


def foot_k(prj, pat, B=None, alpha=None):
    """단부 스프링 K = kV·B·1.0,  kV = kV0·(BV/0.3)^(-3/4),  kV0 = α·E0/0.3,  BV = √(B·1.0)  (도로교설계기준 지반반력계수)"""
    B = B or prj.foot["B"]; alpha = alpha or prj.foot["alpha"]
    kv0 = alpha * prj.patterns[pat]["E0"] / 0.3
    kv = kv0 * (math.sqrt(B * 1.0) / 0.3) ** (-0.75)
    return kv * B * 1.0, kv


def element_loads(g, PV, Pw, fH, fW, pv_mode, pw_mode="normal"):
    """요소별 전역 등분포하중 (qx, qz) [kN/m, 요소 길이당]."""
    out = {}
    for e in g["elems"]:
        nx, nz = e["n"]
        qx = qz = 0.0
        if fH:
            if pv_mode == "vertical":
                if nz > 0:
                    qz += -fH * PV * abs(e["dx"]) / e["L"]
            elif pv_mode == "normal":
                qx += -fH * PV * nx
                qz += -fH * PV * nz
            elif pv_mode in ("ncos", "ncos2"):
                if nz > 0:
                    p = fH * PV * (nz if pv_mode == "ncos" else nz * nz)
                    qx += -p * nx
                    qz += -p * nz
            else:
                raise ValueError(pv_mode)
        if fW:
            if pw_mode == "normal":
                qx += -fW * Pw * nx
                qz += -fW * Pw * nz
            elif pw_mode == "ncos":
                if nz > 0:
                    p = fW * Pw * nz
                    qx += -p * nx
                    qz += -p * nz
            elif pw_mode == "vertical":
                if nz > 0:
                    qz += -fW * Pw * abs(e["dx"]) / e["L"]
            else:
                raise ValueError(pw_mode)
        out[e["id"]] = (qx, qz)
    return out


def write_mct(prj, pat, g, path, pv_mode, sup="pin", pw_mode="normal", efac=1.0, ah=1.0, S=None, combos=None):
    S = S or prj.sect(pat)
    combos = combos if combos is not None else prj.combos(pat)
    MAT = prj.mat
    GND0, LINK_LEN = prj.gnd0, prj.link_len
    nn = len(g["nodes"])
    L = []
    w = L.append
    w("*VERSION\n   9.7.5\n")
    w("*UNIT    ; Unit System\n   KN   , M, KCAL, C\n")
    w("*STRUCTYPE    ; Structure Type\n     1, 1, 1, NO, YES, 9.806, 0, NO, NO, NO\n")
    w("*NODE    ; Nodes")
    for i, (x, z) in enumerate(g["nodes"], start=1):
        w("  %5d, %.6f, 0, %.6f" % (i, x, z))
    for i, (x, z) in enumerate(g["nodes"], start=1):
        nx, nz = g["normals"][i - 1]
        if prj.spring_dir == "horizontal":
            nx, nz = (1.0 if nx >= 0 else -1.0), 0.0
        w("  %5d, %.6f, 0, %.6f" % (GND0 + i, x + LINK_LEN * nx, z + LINK_LEN * nz))
    if sup == "spring":
        for k, (a, b) in enumerate(((0, 1), (nn - 1, nn - 2)), start=1):
            (xa, za), (xb, zb) = g["nodes"][a], g["nodes"][b]
            d = math.hypot(xa - xb, za - zb); ux, uz = (xa - xb) / d, (za - zb) / d
            w("  %5d, %.6f, 0, %.6f" % (GND0 + nn + k, xa + LINK_LEN * ux, za + LINK_LEN * uz))
    w("")
    w("*MATERIAL    ; Material")
    w("    1, CONC , LINING_C%-10g, 0, 0, , C, NO, 0.05, 2, %.4e, %.2f, %.4e, %.3f, 0" % (
        prj.fck, MAT["E"] * efac, MAT["nu"], MAT["alpha"], MAT["gamma"]))
    w("")
    tsec = {}
    for e in g["elems"]:
        tmm = int(round(e["t"] * 1000))
        tsec.setdefault(tmm, len(tsec) + 1)
        e["sect"] = tsec[tmm]
        e["t_model"] = tmm / 1000.0
    w("*SECTION    ; Section")
    for tmm, sid in sorted(tsec.items(), key=lambda kv: kv[1]):
        w("    %d, DBUSER    , T%03d              , CC, 0, 0, 0, 0, 0, 0, YES, NO, SB , 2, %.3f, 1, 0, 0, 0, 0, 0, 0, 0, 0" % (
            sid, tmm, tmm / 1000.0))
    w("")
    w("*ELEMENT    ; Elements")
    for e in g["elems"]:
        beta = 180 if e["dx"] < 0 else 0          # 국부 z 를 항상 외향으로 (M+ = 내면 인장)
        e["beta"] = beta
        w("  %5d, BEAM  , 1, %5d, %5d, %5d, %d, 0" % (e["id"], e["sect"], e["i"], e["j"], beta))
    w("")
    w("*CONSTRAINT    ; Supports")
    if sup == "spring":
        w("   1to%d, 010101, " % nn)
        w("   %dto%d, 111111, " % (GND0 + 1, GND0 + nn + 2))
    else:
        w("   1 %d, %s, " % (nn, {"pin": "111101", "roller": "011101", "fix": "111111"}[sup]))
        w("   2to%d, 010101, " % (nn - 1))
        w("   %dto%d, 111111, " % (GND0 + 1, GND0 + nn))
    w("")
    w("*STLDCASE    ; Static Load Cases")
    for name, f in combos:
        w("   %s, USER, %s" % (name, " ".join("%s%.2f" % (k, v) for k, v in f.items())))
    w("")
    for name, f in combos:
        w("*USE-STLD, %s\n" % name)
        if f.get("D"):
            w("*SELFWEIGHT    ; Self Weight\n0, 0, %.4f, \n" % (-f["D"]))
        fH = f.get("H", 0)
        if fH and abs(fH - 1.0) > 1e-9:
            fH *= ah
        q = element_loads(g, S["PV"], S["Pw"], fH, f.get("W", 0), pv_mode, pw_mode)
        rows = []
        for eid, (qx, qz) in q.items():
            for d, v in (("GX", qx), ("GZ", qz)):
                if abs(v) > 1e-9:
                    rows.append("  %5d, BEAM   , UNILOAD, %s, NO , NO, LY, , , , 0, %.5f, 1, %.5f, 0, 0, 0, 0, , NO, 0, 0, NO, " % (
                        eid, d, v, v))
        if rows:
            w("*BEAMLOAD    ; Element Beam Loads")
            L.extend(rows)
            w("")
        w("; End of data for load case [%s] -------------------------\n" % name)
    w("*ENDDATA")
    with open(path, "w", encoding="cp949") as f:
        f.write("\n".join(L) + "\n")
    return tsec


def link_json(prj, g, Ks):
    body = {"Assign": {}}
    Ls = [e["L"] for e in g["elems"]]
    nn = len(g["nodes"]); GND0 = prj.gnd0
    ks = []
    for i in range(1, nn + 1):
        trib = 0.5 * ((Ls[i - 2] if i > 1 else 0.0) + (Ls[i - 1] if i < nn else 0.0))
        k = Ks * trib * 1.0
        ks.append(k)
        body["Assign"][str(i)] = {"NODE": [i, GND0 + i], "LINK": "COMP", "ANGLE": 0, "SDR": [k, 0, 0, 0, 0, 0],
                                  "bSHEAR": False, "DR": [0.5, 0.5], "BNGR_NAME": ""}
    return body, ks


def temp_json(g, combos):
    et, gt = {"Assign": {}}, {"Assign": {}}
    for e in g["elems"]:
        items_t, items_g = [], []
        for name, f in combos:
            if f.get("T"):
                items_t.append({"ID": len(items_t) + 1, "LCNAME": name, "GROUP_NAME": "", "TEMP": f["T"]})
            if f.get("G"):
                # G = T내면 − T외면. 국부 z 외향 → TZ = T(+z) − T(−z) = −G
                items_g.append({"ID": len(items_g) + 1, "LCNAME": name, "GROUP_NAME": "", "TYPE": 1,
                                "TZ": -f["G"], "USE_HZ": True, "TY": 0, "USE_HY": True})
        if items_t:
            et["Assign"][str(e["id"])] = {"ITEMS": items_t}
        if items_g:
            gt["Assign"][str(e["id"])] = {"ITEMS": items_g}
    return et, gt


def table(c, ttype, keys, cases, fmt="Fixed", place=4):
    r = c.post("/post/table", {"Argument": {
        "TABLE_NAME": "SS_Table", "TABLE_TYPE": ttype, "UNIT": {"FORCE": "KN", "DIST": "M"},
        "STYLES": {"FORMAT": fmt, "PLACE": place}, "NODE_ELEMS": {"KEYS": keys},
        "LOAD_CASE_NAMES": ["%s(ST)" % n for n in cases],
        **({"PARTS": ["PartI", "PartJ"]} if ttype == "BEAMFORCE" else {})}})
    if "SS_Table" not in r:
        raise RuntimeError("%s 표 실패: %s" % (ttype, json.dumps(r, ensure_ascii=False)[:300]))
    return r["SS_Table"]


def run_opts(prj, tag):
    """lining.json "runs" 의 태그 정의 → run() 인자"""
    r = dict(prj.runs_cfg[tag])
    r.pop("tag"); r.pop("_설명", None)
    pat = r.pop("pattern")
    return pat, r


def run(prj, pat, tag=None, sup="pin", pv_mode="ncos", pw_mode="ncos", kfac=1.0, efac=1.0, foot_b=None, foot_alpha=None,
        ah=1.0, geom_override=None, S=None, combos=None, write_only=False, runs_dir=None):
    from midas_api import Civil
    tag = tag or pat
    S = S or prj.sect(pat)
    combos = combos if combos is not None else prj.combos(pat)
    g = geom_override() if geom_override else G.build(prj)
    RUNS = runs_dir or prj.runs
    os.makedirs(RUNS, exist_ok=True)
    mct = os.path.join(RUNS, "%s.mct" % tag)
    tsec = write_mct(prj, pat, g, mct, pv_mode, sup, pw_mode, efac, ah, S, combos)
    names = [n for n, _ in combos]
    nn, ne = len(g["nodes"]), len(g["elems"])
    print("[%s] MCT %s — 절점 %d(+지반 %d), 요소 %d, 단면 %d종, 하중케이스 %s, PV=%s" % (
        tag, os.path.basename(mct), nn, nn, ne, len(tsec), names, pv_mode))
    if write_only:
        return {"mct": mct, "geom": g}
    GND0 = prj.gnd0
    c = Civil(timeout=900)
    c.post("/doc/SAVEAS", {"Argument": os.path.join(RUNS, "_scratch.mcb")})
    c.post("/doc/NEW", {"Argument": {}})
    c.post("/doc/IMPORTMXT", {"Argument": mct})
    n_node, n_elem = c.node_count(), c.elem_count()
    extra = 2 if sup == "spring" else 0
    print("  임포트: 절점 %d, 요소 %d" % (n_node, n_elem))
    assert (n_node, n_elem) == (2 * nn + extra, ne), "임포트 개수 불일치 — MCT 파싱 실패 의심"

    body, ks = link_json(prj, g, S["Ks"] * kfac)
    kfoot = None
    if sup == "spring":
        kfoot, kv = foot_k(prj, pat, foot_b, foot_alpha)
        for k, i in ((1, 1), (2, nn)):
            body["Assign"][str(nn + k)] = {"NODE": [i, GND0 + nn + k], "LINK": "COMP", "ANGLE": 0,
                                           "SDR": [kfoot, 0, 0, 0, 0, 0], "bSHEAR": False, "DR": [0.5, 0.5], "BNGR_NAME": ""}
        print("  단부 스프링: kv = %.0f kN/m³, K = kv·B = %.0f kN/m (B %.2f m, α %.1f, E0 %.0f MPa)" % (
            kv, kfoot, foot_b or prj.foot["B"], foot_alpha or prj.foot["alpha"], prj.patterns[pat]["E0"] / 1e3))
    c.put("/db/ELNK", body)
    back = c.get("/db/ELNK").get("ELNK", {})
    types = {v.get("LINK") for v in back.values()}
    print("  탄성링크 %d개, 형식 %s, k 범위 %.0f~%.0f kN/m" % (len(back), types, min(ks), max(ks)))
    assert len(back) == nn + extra and types == {"COMP"}, "압축전용 링크 되읽기 실패"
    if S.get("temp"):
        et, gt = temp_json(g, combos)
        c.put("/db/ETMP", et)
        c.put("/db/GTMP", gt)
        be, bg = c.get("/db/ETMP").get("ETMP", {}), c.get("/db/GTMP").get("GTMP", {})
        print("  요소온도 %d요소, 온도구배 %d요소" % (len(be), len(bg)))
        assert len(be) == ne and len(bg) == ne
    c.post("/doc/SAVEAS", {"Argument": os.path.join(RUNS, "%s.mcb" % tag)})
    t = time.time()
    c.post("/doc/ANAL", {"Assign": {}})
    print("  해석 %.0fs" % (time.time() - t))
    c.post("/doc/EXPORTMXT", {"Argument": os.path.join(RUNS, "%s_export.mct" % tag)})
    bf = table(c, "BEAMFORCE", list(range(1, ne + 1)), names, place=3)
    rx = table(c, "REACTIONG", list(range(1, nn + 1)) + list(range(GND0 + 1, GND0 + nn + 1 + extra)), names, place=3)
    dp = table(c, "DISPLACEMENTG", list(range(1, nn + 1)), names, fmt="Scientific", place=4)
    out = {"sec": pat, "tag": tag, "ah": ah, "pv_mode": pv_mode, "pw_mode": pw_mode, "kfac": kfac, "efac": efac, "sup": sup,
           "S": S, "combos": combos,
           "geom": {"nodes": g["nodes"], "normals": g["normals"],
                    "elems": [{k: e[k] for k in ("id", "i", "j", "L", "t", "t_model", "n", "reg", "dx", "beta")} for e in g["elems"]]},
           "k_link": ks, "k_foot": kfoot, "foot_b": foot_b or prj.foot.get("B"), "foot_alpha": foot_alpha or prj.foot.get("alpha"),
           "BEAMFORCE": bf, "REACTIONG": rx, "DISPLACEMENTG": dp}
    json.dump(out, open(os.path.join(RUNS, "%s_result.json" % tag), "w", encoding="utf-8"), ensure_ascii=False)
    print("  결과 저장: %s_result.json" % tag)
    return out


def run_tag(prj, tag, **kw):
    pat, opts = run_opts(prj, tag)
    opts.update(kw)
    return run(prj, pat, tag=tag, **opts)
