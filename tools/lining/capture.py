# -*- coding: utf-8 -*-
"""
NX 화면 캡처 — 모델도·축력도·전단력도·모멘트도·변형도 → <프로젝트>/runs/cap/<태그>_<조합>_N|V|M|D.jpg
모델을 다시 해석해 결과를 NX 메모리에 올린 뒤 /view/CAPTURE 로 저장한다(해석 태그 정의는 lining.json "runs").
"""
import os, json
from . import model as MD

VIEW = {"HORIZONTAL": 0, "VERTICAL": 0}


def cap(c, out_dir, name, arg, size=(2400, 1500)):
    a = dict(arg)
    a.update({"SET_HIDDEN": False, "EXPORT_PATH": os.path.join(out_dir, name + ".jpg"), "WIDTH": size[0], "HEIGHT": size[1]})
    try:
        r = c.post("/view/CAPTURE", {"Argument": a})
        ok = os.path.exists(a["EXPORT_PATH"])
        print("  %-22s %s %s" % (name, "OK" if ok else "없음", json.dumps(r, ensure_ascii=False)[:80]))
        return ok
    except Exception as e:
        print("  %-22s 실패 %s" % (name, str(e)[:160]))
        return False


def beam(lc, comp, values=True):
    return {"SET_MODE": "post", "ANGLE": VIEW, "DISPLAY": {"PERSPECTIVE": False, "ZOOM_LEVEL": 100},
            "RESULT_GRAPHIC": {"CURRENT_MODE": "beamdiagrams", "LOAD_CASE_COMB": {"TYPE": "ST", "NAME": lc},
                               "COMPONENTS": {"PART": "total", "COMP": comp},
                               "DISPLAY_OPTIONS": {"FIDELITY": "Exact", "FILL": "line fill", "SCALE": 1.0},
                               "TYPE_OF_DISPLAY": {"CONTOUR": {"OPT_CHECK": True}, "LEGEND": {"OPT_CHECK": True},
                                                   "VALUES": {"OPT_CHECK": values, "DECIMAL_PT": 1, "VALUE_EXP": False}}}}


def deform(lc):
    return {"SET_MODE": "post", "ANGLE": VIEW, "DISPLAY": {"PERSPECTIVE": False, "ZOOM_LEVEL": 100},
            "RESULT_GRAPHIC": {"CURRENT_MODE": "deformedshape", "LOAD_CASE_COMB": {"TYPE": "ST", "NAME": lc},
                               "COMPONENTS": {"COMP": "DXZ"},
                               "TYPE_OF_DISPLAY": {"UNDEFORMED": {"OPT_CHECK": True}, "LEGEND": {"OPT_CHECK": True}, "VALUES": {"OPT_CHECK": False}}}}


def capture(prj, tag, lcs=None, rerun=True):
    """lcs 없으면 강도·사용 조합 전부(aux 제외)."""
    from midas_api import Civil
    os.makedirs(prj.cap, exist_ok=True)
    pat, _ = MD.run_opts(prj, tag)
    if lcs is None:
        roles = prj.combo_roles[prj.patterns[pat]["combos"]]
        lcs = [n for n, _ in prj.combos(pat) if roles.get(n) in ("strength", "service")]
    if rerun:
        MD.run_tag(prj, tag)
    c = Civil(timeout=300)
    cap(c, prj.cap, "%s_model" % tag, {"SET_MODE": "pre", "ANGLE": VIEW,
                                       "DISPLAY": {"NODE": {"NODE": True, "NODE_NUMBER": False}, "ELEMENT": {"ELEMENT_NUMBER": True},
                                                   "PERSPECTIVE": False, "ZOOM_LEVEL": 100}})
    ok = True
    for lc in lcs:
        for comp, t in (("Fx", "N"), ("Fz", "V"), ("My", "M")):
            ok &= cap(c, prj.cap, "%s_%s_%s" % (tag, lc, t), beam(lc, comp))
        cap(c, prj.cap, "%s_%s_D" % (tag, lc), deform(lc))
    return ok
