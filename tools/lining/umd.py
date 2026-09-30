# -*- coding: utf-8 -*-
"""
midas UMD 입력 — 철근 라이닝의 강도조합 단면력을 UMD RC/Wall '설계부재력 입력' 계수하중 표로.

  python -m lining umd <프로젝트> <태그> [부재번호…]

- 아치부(reg A) 전 부재는 한 표로(두께가 같을 때), 측벽부는 부재를 지정하거나(없으면 report_data.json 의
  "측벽|pm" 지배 부재) 부재마다 한 표로 만든다 — UMD 단면 하나는 두께 하나다.
- 출력 runs/umd/<태그>_<이름>.tsv: 열 = 구분 | Pu | Mu | Vu (Pu 압축 +, Mu = MIDAS Moment-y, Vu = Shear-z),
  CRLF·빈 줄 없음(빈 줄이 있으면 UMD 가 "붙여넣을 내용이 테이블의 범위를 벗어납니다"). 구분 = <조합>_<부재><i|j>.
- runs/umd/<태그>_UMD설정.txt: 단면별 H·Dt·Db, fck·fy, 상·하단 철근(개수/m) — UMD 단면 탭에 넣을 값.
UMD 조작·그림 추출은 core/tools/umd_auto.py, umd_pm.py 와 스킬 tunnel-lining 의 umd_pm.md.
"""
import os, json
from . import post as LP


def _rows(R, lc_list, elems):
    out = []
    for lc in lc_list:
        for e in elems:
            d = R["F"][lc][e]
            for part in ("I", "J"):
                ax, vz, my = d[part]
                out.append((f"{lc}_{e}{part.lower()}", -ax, my, vz))
    return out


def _write(path, rows):
    txt = "\r\n".join("\t".join([n] + [f"{v:.3f}" for v in vals]) for n, *vals in rows)
    open(path, "w", encoding="utf-8", newline="").write(txt)


def make(prj, tag, wall_elems=None):
    R = LP.load(prj.result_path(tag))
    sec = R["sec"]
    if sec not in prj.rc_patterns():
        raise SystemExit(f"{tag}: 패턴 {sec} 은 철근(rc) 패턴이 아니다 — UMD P-M 대상 아님")
    strength = [lc for lc in prj.roles(sec, "strength") if lc in R["F"] and lc in prj.check.get("strength_cases", [lc])]
    E = {e["id"]: e for e in R["geom"]["elems"]}
    h = lambda e: round(E[e].get("t_model", E[e]["t"]), 3)
    arch = sorted(e for e in E if E[e]["reg"] == "A")
    if not wall_elems:
        rd = os.path.join(prj.runs, "report_data.json")
        try:
            wall_elems = [json.load(open(rd, encoding="utf-8"))["sections"][tag]["checks"]["측벽|pm"]["elem"]]
        except (OSError, KeyError):
            raise SystemExit("측벽 부재를 지정하거나 먼저 `python -m lining data` 로 report_data.json 을 만든다")
    out_dir = os.path.join(prj.runs, "umd"); os.makedirs(out_dir, exist_ok=True)
    groups = {}
    for e in arch: groups.setdefault(("ARCH", h(e)), []).append(e)
    for e in wall_elems: groups[(f"WALL{e}", h(e))] = [e]
    rc = prj.check.get("rc", {})
    n_bar = round(1000.0 / rc["s_bar"]) if rc.get("s_bar") else None
    lines = [f"태그 {tag} (패턴 {sec}) — midas UMD RC/Wall, Design Option KCI-USD12, 평형조건 Mu/Pu = φMn/φPn",
             f"fck {prj.fck} MPa, fy {rc.get('fy')} MPa, 철근 D{rc.get('bar', 0):.0f}@{rc.get('s_bar')} 상·하단 각 {n_bar}개/m (As 각 {rc.get('As')} mm²),"
             f" Dt = Db = 철근 중심 {rc.get('dc')} mm, B = 1.000 m, 철근량비율 자동결정·전단검토·확대모멘트 끔",
             f"강도조합: {', '.join(strength)}", ""]
    for (name, hh), els in groups.items():
        if name == "ARCH" and len({h(e) for e in els}) > 1:
            raise SystemExit("아치부 두께가 부재마다 다르다 — 부재를 나눠 지정할 것")
        rows = _rows(R, strength, els)
        p = os.path.join(out_dir, f"{tag}_{name}.tsv"); _write(p, rows)
        lines.append(f"{name}: H {hh:.3f} m, 부재 {els[0]}∼{els[-1]} ({len(rows)}행) → {os.path.basename(p)}")
        print(f"{name}: H {hh:.3f} m, {len(rows)}행 → {p}")
    open(os.path.join(out_dir, f"{tag}_UMD설정.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:3]))
