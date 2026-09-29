# -*- coding: utf-8 -*-
"""
라이닝 도심선 격자 — 표준단면도 DXF 의 라이닝 내·외면 원호(3심원, 인버트 없음)에서.

입력(lining.json "geometry"):
  dxf        표준단면도 DXF (프로젝트 기준 상대경로)
  layer      라이닝 원호 레이어(예: CS-CONC)
  origin_mm  [x, y] 터널 중심선 × 노면 EL 0 의 도면 좌표 [mm]
  sheet_x_mm [x0, x1] 해석할 단면(시트)의 도면 x 범위 — 같은 도면에 편경사별 단면이 여러 개일 때
  n_elem     {"L": 좌측벽, "A": 아치, "R": 우측벽 요소 수} — 설계 부재번호도와 같게
  arcs       (선택) DXF 대신 원호를 직접: {"R1_in": [cx, cz, R, a0, a1], "R1_out", "L_in", "L_out", "R_in", "R_out"} [m, 도]

제한: 천단 동심 원호 2개(중심 x = 0) + 좌·우 측벽 원호 각 2개 = 6개 원호인 3심원 단면만. 인버트·5심원은 두 번째
터널에서 필요해지면 확장한다(검증 대상 없이 미리 만들지 않음).

주의: 치수(DIMENSION) 값은 쓰지 않는다 — 읍애터널 표준단면도의 'R1=<>' 치수 5040.57 은 반경이 아니라
6580·cos40° 수평거리였다. 반경·중심은 ARC 개체에서만 읽는다.
좌표: 원점 = 터널 중심선 × 노면 EL 0, x 우측 +, z 위 +, 단위 m. 각도는 각 원호 중심 기준 +x 축에서 반시계.
"""
import math


class Arc:
    def __init__(self, cx, cz, R, a0, a1, tag):
        self.cx, self.cz, self.R, self.a0, self.a1, self.tag = cx, cz, R, a0, a1, tag

    def pt(self, a):
        r = math.radians(a)
        return (self.cx + self.R * math.cos(r), self.cz + self.R * math.sin(r))

    def u(self, a):
        r = math.radians(a)
        return (math.cos(r), math.sin(r))

    def __repr__(self):
        return "<%s c=(%.4f,%.4f) R=%.5f %.3f~%.3f°>" % (self.tag, self.cx, self.cz, self.R, self.a0, self.a1)


def read_arcs(prj):
    G = prj.cfg["geometry"]
    mk = lambda a, t: Arc(a[0], a[1], a[2], a[3], a[4], t)
    if G.get("arcs"):
        A = G["arcs"]
        return {"R1_in": mk(A["R1_in"], "R1_in"), "R1_out": mk(A["R1_out"], "R1_out"), "L_in": mk(A["L_in"], "R2L_in"),
                "L_out": mk(A["L_out"], "R2L_out"), "R_in": mk(A["R_in"], "R2R_in"), "R_out": mk(A["R_out"], "R2R_out")}
    import ezdxf
    doc = ezdxf.readfile(prj.path(G["dxf"]))
    X0, Y0 = G["origin_mm"]; SX = G["sheet_x_mm"]
    arcs = []
    for e in doc.modelspace():
        if e.dxftype() != "ARC" or e.dxf.layer != G["layer"]:
            continue
        c = e.dxf.center
        if not (SX[0] < c.x < SX[1]):
            continue
        arcs.append(((c.x - X0) / 1000.0, (c.y - Y0) / 1000.0, e.dxf.radius / 1000.0, e.dxf.start_angle, e.dxf.end_angle))
    if len(arcs) != 6:
        raise ValueError("%s 원호가 6개가 아니다(%d) — sheet_x_mm/layer 확인" % (G["layer"], len(arcs)))
    crown = sorted([a for a in arcs if abs(a[0]) < 1e-3], key=lambda a: a[2])
    left = sorted([a for a in arcs if a[0] < -1e-3], key=lambda a: a[2])
    right = sorted([a for a in arcs if a[0] > 1e-3], key=lambda a: a[2])
    if not (len(crown) == len(left) == len(right) == 2):
        raise ValueError("원호 분류 실패(천단 동심 2 + 좌 2 + 우 2 가 아님): %s" % arcs)
    return {"R1_in": mk(crown[0], "R1_in"), "R1_out": mk(crown[1], "R1_out"), "L_in": mk(left[0], "R2L_in"),
            "L_out": mk(left[1], "R2L_out"), "R_in": mk(right[0], "R2R_in"), "R_out": mk(right[1], "R2R_out")}


def _thick(P, n, outer):
    dx, dz = P[0] - outer.cx, P[1] - outer.cz
    b = dx * n[0] + dz * n[1]
    c = dx * dx + dz * dz - outer.R ** 2
    return -b + math.sqrt(b * b - c)


def outer_polygon(A, n=720):
    Lo, Co, Ro = A["L_out"], A["R1_out"], A["R_out"]
    pts = []
    for i in range(n + 1):
        pts.append(Lo.pt(Lo.a1 + (Lo.a0 - Lo.a1) * i / n))
    for i in range(1, n + 1):
        pts.append(Co.pt(Co.a1 + (Co.a0 - Co.a1) * i / n))
    a_end = Ro.a0 - 360.0
    for i in range(1, n + 1):
        pts.append(Ro.pt(Ro.a1 + (a_end - Ro.a1) * i / n))
    return pts


def poly_area(pts):
    s = 0.0
    for (x1, z1), (x2, z2) in zip(pts, pts[1:] + pts[:1]):
        s += x1 * z2 - x2 * z1
    return abs(s) / 2.0


def mesh(A, nL, nA, nR):
    Li, Ci, Ri = A["L_in"], A["R1_in"], A["R_in"]
    Lo, Co, Ro = A["L_out"], A["R1_out"], A["R_out"]
    seq = []
    for i in range(nL):
        seq.append((Li, Lo, Li.a1 + (Li.a0 - Li.a1) * i / nL, "L"))
    for i in range(nA):
        seq.append((Ci, Co, Ci.a1 + (Ci.a0 - Ci.a1) * i / nA, "A"))
    a_end = Ri.a0 - 360.0
    for i in range(nR + 1):
        seq.append((Ri, Ro, Ri.a1 + (a_end - Ri.a1) * i / nR, "R"))
    nodes, normals, t_node, region, inner = [], [], [], [], []
    for ai, ao, a, reg in seq:
        P = ai.pt(a); n = ai.u(a); t = _thick(P, n, ao)
        nodes.append((P[0] + 0.5 * t * n[0], P[1] + 0.5 * t * n[1]))
        normals.append(n); t_node.append(t); region.append(reg); inner.append(P)
    return nodes, normals, t_node, region, inner


def build(prj):
    ne_cfg = prj.cfg["geometry"]["n_elem"]
    nL, nA, nR = ne_cfg["L"], ne_cfg["A"], ne_cfg["R"]
    A = read_arcs(prj)
    nodes, normals, t_node, region, inner = mesh(A, nL, nA, nR)
    elems = []
    for i in range(len(nodes) - 1):
        (x1, z1), (x2, z2) = nodes[i], nodes[i + 1]
        L = math.hypot(x2 - x1, z2 - z1)
        tx, tz = (x2 - x1) / L, (z2 - z1) / L
        nx, nz = -tz, tx                              # 절점 순서 좌→천단→우(시계) → 반시계 90° = 외향
        reg = "A" if (region[i] == "A" and region[i + 1] in ("A", "R") and nL <= i < nL + nA) else \
              ("L" if i < nL else ("A" if i < nL + nA else "R"))
        t = 0.5 * (t_node[i] + t_node[i + 1])
        elems.append({"id": i + 1, "i": i + 1, "j": i + 2, "L": L, "t": t, "n": (nx, nz), "reg": reg, "dx": x2 - x1})
    poly = outer_polygon(A)
    xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    geo = {"arcs": {k: [v.cx, v.cz, v.R, v.a0, v.a1] for k, v in A.items()},
           "B_outer": max(xs) - min(xs), "Ht_outer": max(zs) - min(zs), "A_outer": poly_area(poly),
           "nodes": nodes, "normals": normals, "t_node": t_node, "inner": inner, "elems": elems,
           "n_elem": {"L": nL, "A": nA, "R": nR}}
    geo["R_eq"] = math.sqrt(geo["A_outer"] / math.pi)
    return geo


def report(prj, g=None):
    """형상 점검 출력 — 설계값(lining.json "design_check")과 대조"""
    g = g or build(prj)
    dc = prj.cfg.get("design_check", {})
    for k, v in g["arcs"].items():
        print("%-7s c=(%8.4f,%8.4f) R=%8.5f  %8.3f~%8.3f" % (k, *v))
    print("  B (외면 최대폭) = %.3f m   (설계 %s)" % (g["B_outer"], dc.get("B", "-")))
    print("  Ht(외면 천단~기초저면) = %.3f m   (설계 %s)" % (g["Ht_outer"], dc.get("Ht", "-")))
    print("  A (외면 내부면적) = %.3f m²  (설계 %s)" % (g["A_outer"], dc.get("A", "-")))
    print("  R = √(A/π) = %.3f m   (설계 %s)" % (g["R_eq"], dc.get("R", "-")))
    print("  절점 %d, 요소 %d, 두께 좌측벽 %.3f~%.3f / 우측벽 %.3f~%.3f" % (
        len(g["nodes"]), len(g["elems"]),
        min(e["t"] for e in g["elems"] if e["reg"] == "L"), max(e["t"] for e in g["elems"] if e["reg"] == "L"),
        min(e["t"] for e in g["elems"] if e["reg"] == "R"), max(e["t"] for e in g["elems"] if e["reg"] == "R")))
    Atot = sum(e["L"] * e["t"] for e in g["elems"])
    print("  라이닝 면적(모델) %.3f m² → 자중 %.1f kN/m (γ=%s)" % (Atot, prj.mat["gamma"] * Atot, prj.mat["gamma"]))
    return g
