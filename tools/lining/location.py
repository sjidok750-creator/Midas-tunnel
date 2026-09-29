# -*- coding: utf-8 -*-
"""
검토 위치도 — 실시설계 평면·종단면도 배치(layout)의 도곽 전체를 플롯처럼 흑백으로 출력하고 검토 구간을 표기한다.
출력: <프로젝트>/runs/fig/rpt_location.png  (lining.json "location")

손으로 넣는 상수와 찾는 법(실증 프로젝트 lining.json 참고 — 로컬)
  sheets[].x0, s0, s1   종단면 측점표 '측점' 행 문자의 x 와 그 측점(20 m 간격) → x = x0 + (STA − s0). 시트마다.
  sheets[].el_offset    종단면 표고 축 문자(예 "250.00")의 y 로: y = EL − el_offset
  sheets[].frame        도곽: 배치의 INSERT '도각'(또는 '도각박스') virtual_entities 중 CX-BORD-LIN1 폴리라인 범위 ± 3 mm
  plan.viewports        평면도 VIEWPORT id — 뷰포트 변환(get_transformation_matrix)으로 모델공간 측점 기호를 배치 좌표로 옮긴다
  ground_row            측점표 '지반고' 행의 y 범위(세로쓰기 문자 rotation 90)
  grade                 계획고 = el0 + slope·(STA − sta0) (측점표 '계획고' 행으로 확인)
  crown_above_grade     라이닝 외면 천단고 − 계획고, invert_below_grade  계획고 − 인버트(기초 저면)
주의: ColorPolicy 는 MONOCHROME_LIGHT_BG — COLOR_SWAP_BW 는 종단 지반선을 지운다(2026-09 실증).
"""
import os, time, re, bisect
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy, LineweightPolicy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

plt.rcParams["font.family"] = "Malgun Gothic"
INK_TXT = "#222222"


class Loc:
    def __init__(self, prj):
        self.prj = prj
        self.c = prj.cfg["location"]
        self.sheets = sorted(self.c["sheets"], key=lambda s: s["s0"])
        g = self.c["grade"]
        self.g_sta0, self.g_el0, self.g_slope = g["sta0"], g["el0"], g["slope"]
        self.crown = self.c.get("crown_above_grade", 7.38)
        self.invert = self.c.get("invert_below_grade", 0.58)

    def sheet_of(self, sta):
        for s in self.sheets[:-1]:
            if sta < s["s1"]:
                return s
        return self.sheets[-1]

    def xp(self, sta):
        s = self.sheet_of(sta)
        return s["x0"] + (sta - s["s0"])

    def y_el(self, el, sta):
        return el - self.sheet_of(sta)["el_offset"]

    def grade(self, sta):
        return self.g_el0 + self.g_slope * (sta - self.g_sta0)

    def pieces(self, a, b):
        """구간을 시트 경계에서 나눈다(앞 시트 끝은 경계 직전까지 — 경계 측점은 다음 시트 좌표)."""
        out = []
        for k, s in enumerate(self.sheets):
            last = k == len(self.sheets) - 1
            lo = max(a, s["s0"]) if k else a
            hi = b if last else min(b, s["s1"] - 0.001)
            if hi - lo > 0.01:
                out.append((lo, hi))
        return out


def sta_txt(sta):
    return "%d+%05.1f" % (int(sta // 1000), sta % 1000)


def plan_ticks(L, doc):
    P = L.c["plan"]
    msp = doc.modelspace(); lay = doc.layouts.get(L.c["layout"]); out = []
    for v in lay.query("VIEWPORT"):
        if v.dxf.id not in P["viewports"]: continue
        m = v.get_transformation_matrix(); lim = v.get_modelspace_limits(); d = v.dxf
        inside = lambda q: abs(q.x - d.center.x) <= d.width / 2 and abs(q.y - d.center.y) <= d.height / 2
        ticks, labels = {}, []
        for e in msp.query("INSERT TEXT"):
            if P["sta_layer"] not in e.dxf.layer: continue
            p = e.dxf.insert
            if not (lim[0] <= p.x <= lim[2] and lim[1] <= p.y <= lim[3]): continue
            q = m.transform(p)
            if not inside(q): continue
            if e.dxftype() == "INSERT" and P.get("tick_block", "측점") in e.dxf.name:
                key = (round(q.x, 1), round(q.y, 1))
                ticks[key] = ticks.get(key, False) or (P.get("main_block", "주측점") in e.dxf.name)
            elif e.dxftype() == "TEXT":
                s = e.dxf.text.strip()
                if re.fullmatch(r"(?:(\d)\+)?(\d{3})", s): labels.append((q.x, q.y, s))
        ts = sorted(ticks.items())
        mains = [k for k, (xy, main) in enumerate(ts) if main]
        full = [l for l in labels if "+" in l[2]]
        assert full, ("뷰포트 %d: km 표기 측점 라벨 없음" % d.id, labels)
        x, y, s = full[0]
        k0 = min(mains, key=lambda k: abs(ts[k][0][0] - x))
        base = (int(s.split("+")[0]) * 1000 + int(s.split("+")[1])) if "+" in s else P.get("km_default", 0) + int(s)
        for k, (xy, main) in enumerate(ts):
            out.append((base + 20.0 * (k - k0), xy[0], xy[1], main))
    out.sort()
    bad = [t for t in out if (t[0] % 100 == 0) != t[3]]
    assert not bad, ("평면 측점 대응 오류", bad[:5])
    return out


def plan_xy(ticks, sta):
    for (s0, x0, y0, _), (s1, x1, y1, _) in zip(ticks, ticks[1:]):
        if s0 <= sta <= s1:
            t = (sta - s0) / (s1 - s0); return x0 + t * (x1 - x0), y0 + t * (y1 - y0)
    raise ValueError("평면 측점 범위 밖: %s" % sta)


def ground_table(L, lay):
    gr = L.c["ground_row"]
    pts = []
    for e in lay.query("TEXT"):
        y = e.dxf.insert.y
        if gr["y"][0] < y < gr["y"][1] and abs(e.dxf.get("rotation", 0) - gr.get("rotation", 90)) < 1:
            x = e.dxf.insert.x
            try: el = float(e.dxf.text)
            except ValueError: continue
            sh = None
            for s in L.sheets:
                if s["x0"] - 50 <= x <= s["x0"] + (s["s1"] - s["s0"]) + 50: sh = s
            if sh is None: continue
            pts.append((round(((x - sh["x0"]) + sh["s0"]) / 20) * 20.0, el))
    pts = sorted(set(pts)); xs = [p[0] for p in pts]
    assert len(pts) > 10, len(pts)

    def f(s):
        i = max(1, min(len(xs) - 1, bisect.bisect_left(xs, s)))
        (s0, e0), (s1, e1) = pts[i - 1], pts[i]
        return e0 + (e1 - e0) * (s - s0) / (s1 - s0)
    return f


def render(prj):
    L = Loc(prj); c = L.c
    t0 = time.time()
    doc = ezdxf.readfile(prj.path(c["dxf"]))
    ticks = plan_ticks(L, doc)
    print("평면 측점", ticks[0][:3], "…", ticks[-1][:3], len(ticks), "개")
    for st in doc.styles:
        st.dxf.font = "malgun.ttf"
        if st.dxf.hasattr("bigfont"): st.dxf.discard("bigfont")
    lay = doc.layouts.get(c["layout"])
    txt = " ".join((e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text) for e in lay.query("TEXT MTEXT"))
    for bad in c.get("forbid_text", []):
        assert bad not in txt, "도면 문자에 보고서에서 빼기로 한 표기가 있다: %s" % bad
    fig = plt.figure(figsize=(30, 16)); ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc); ctx.set_current_layout(lay)
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.MONOCHROME_LIGHT_BG,
                        lineweight_policy=LineweightPolicy.RELATIVE, lineweight_scaling=0.35)
    Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(lay, finalize=True)
    print("렌더", round(time.time() - t0, 1), "s")
    gnd = ground_table(L, lay)
    Z = 1e6
    xp, y_el, grade = L.xp, L.y_el, L.grade
    CR, INV = L.crown, L.invert
    # 1) 인버트∼지표까지 칠하는 검토 구간
    for it in c.get("full", []):
        name, a, b, col = it["name"], it["a"], it["b"], it["color"]
        lab_x, lab_el, ha = it["label_at"]
        ss = [a + (b - a) * i / 40 for i in range(41)]
        xs = [xp(s) for s in ss]
        inv = [y_el(grade(s) - INV, s) for s in ss]; crown = [y_el(grade(s) + CR, s) for s in ss]
        top = [y_el(gnd(s), s) for s in ss]
        ax.fill_between(xs, inv, crown, color=col, alpha=0.85, lw=0, zorder=Z)
        ax.fill_between(xs, crown, top, color=col, alpha=0.25, lw=0, zorder=Z)
        ax.plot([xs[0], xs[0]], [inv[0], top[0]], color=col, lw=2.0, zorder=Z); ax.plot([xs[-1], xs[-1]], [inv[-1], top[-1]], color=col, lw=2.0, zorder=Z)
        cov = [gnd(s) - (grade(s) + CR) for s in ss]
        pts = [plan_xy(ticks, s) for s in ss]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=16, alpha=0.9, solid_capstyle="butt", zorder=Z)
        px, py = pts[20]
        dn = it.get("plan_label") == "down"
        ax.annotate(name, xy=(px, py - 4 if dn else py + 4), xytext=(px, py - 30 if dn else py + 30), ha="center", va="top" if dn else "bottom", fontsize=30, color=col,
                    fontweight="bold", zorder=Z + 2, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col, lw=2.2),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=2.2))
        ax.annotate("%s 라이닝 검토 구간\nSTA.%s ∼ %s\n토피 %.1f ∼ %.1f m" % (name, sta_txt(a), sta_txt(b), min(cov), max(cov)),
                    xy=((xs[0] + xs[-1]) / 2, max(top) + 1), xytext=(lab_x, y_el(lab_el, a)), ha=ha, va="center",
                    fontsize=28, color=col, fontweight="bold", zorder=Z + 2,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=col, lw=2.2), arrowprops=dict(arrowstyle="-", color=col, lw=2.0))
        print("%s %s~%s 토피 %.1f~%.1f m (지반고 %.1f~%.1f)" % (name, sta_txt(a), sta_txt(b), min(cov), max(cov), min(gnd(s) for s in ss), max(gnd(s) for s in ss)))

    # 2) 터널 높이만 칠하는 띠 구간
    def band(a, b, col, hatch=None, lw_plan=10):
        for s0, s1 in L.pieces(a, b):
            ss = [s0 + (s1 - s0) * i / 20 for i in range(21)]
            xs = [xp(s) for s in ss]
            inv = [y_el(grade(s) - INV, s) for s in ss]; crown = [y_el(grade(s) + CR, s) for s in ss]
            ax.fill_between(xs, inv, crown, color=col if not hatch else "white", alpha=0.75 if not hatch else 1.0, lw=0, zorder=Z - 2,
                            hatch=hatch, edgecolor=col if hatch else None)
            pts = [plan_xy(ticks, s) for s in ss]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=lw_plan, alpha=0.9, solid_capstyle="butt", zorder=Z - 2)
    covs = {}
    for bd in c.get("bands", []):
        for a, b in bd["segs"]:
            band(a, b, bd["color"], bd.get("hatch"))
            if not bd.get("hatch"):
                ss = [a + (b - a) * i / 20 for i in range(21)]
                covs.setdefault(bd["key"], []).extend(gnd(s) - (grade(s) + CR) for s in ss)
    for key, cv in covs.items():
        print("%s 토피 %.1f ∼ %.1f m" % (key, min(cv), max(cv)))
    # 3) 범례
    lg = c.get("legend")
    if lg:
        s = [sh for sh in L.sheets if sh["id"] == lg["sheet"]][0]
        x0 = s["x0"] + (s["s1"] - s["s0"]) - lg["x_from_right"]
        items = lg["items"]
        for i, (lab, col, hatch) in enumerate(items):
            yy = y_el(lg["el_top"] - lg["dy"] * i, s["s0"])
            ax.add_patch(Rectangle((x0, yy - 2.2), 16, 4.4, facecolor=col if not hatch else "white", edgecolor=col, hatch=hatch, lw=1.2, zorder=Z + 3))
            ax.text(x0 + 20, yy, lab, va="center", ha="left", fontsize=21, color=INK_TXT, zorder=Z + 3)
        ax.add_patch(Rectangle((x0 - 4, y_el(lg["el_top"] - lg["dy"] * (len(items) - 1), s["s0"]) - 5), lg.get("box_w", 128), lg["dy"] * (len(items) - 1) + 10,
                               facecolor="white", edgecolor="#555555", lw=1.0, zorder=Z + 2.5))
    # 4) 띠 구간 설명
    bl = c.get("band_label")
    if bl:
        for sta in bl["at"]:
            ax.text(xp(sta), y_el(grade(sta) + bl["dy_above_grade"], sta), bl["text"], ha="center", va="bottom",
                    fontsize=24, color=bl["color"], fontweight="bold", zorder=Z + 2,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=bl["color"], lw=2.0))
    # 5) 설계 지반해석 단면
    EL_LO = c.get("el_lo", 150.0)
    for sta, pat in c.get("ground_sections", []):
        x = xp(sta)
        ax.plot([x, x], [y_el(EL_LO, sta), y_el(grade(sta) - INV, sta)], color="#2e7d32", lw=3.0, ls=(0, (5, 3)), zorder=Z)
        right = L.sheet_of(sta)["s1"] - sta < 60
        ax.text(x - 2 if right else x + 2, y_el(EL_LO + 3, sta), "설계 지반해석 단면\nSTA.%d+%03d (설계 %s)" % (sta // 1000, sta % 1000, pat), fontsize=24,
                color="#2e7d32", ha="right" if right else "left", va="bottom", zorder=Z + 1,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))
    return L, fig, ax


def make(prj, out_dir=None):
    out_dir = out_dir or prj.fig
    os.makedirs(out_dir, exist_ok=True)
    L, fig, ax = render(prj)
    parts = []
    for s in L.sheets:
        x0, x1, yb, yt = s["frame"]
        ax.set_xlim(x0, x1); ax.set_ylim(yb, yt)
        fig.set_size_inches((x1 - x0) / 25.4, (yt - yb) / 25.4)       # 도면 1 mm → 1 in/25.4
        p = os.path.join(out_dir, "_loc_sheet%d.png" % s["id"])
        fig.savefig(p, dpi=L.c.get("dpi", 200)); parts.append(Image.open(p).convert("RGB")); print(p, parts[-1].size)
    plt.close(fig)
    w = max(p.size[0] for p in parts); gap = L.c.get("gap", 40)
    out = Image.new("RGB", (w, sum(p.size[1] for p in parts) + gap * (len(parts) - 1)), "white")
    y = 0
    for p in parts:
        out.paste(p, (0, y)); y += p.size[1] + gap
    W = L.c.get("out_width", 3200)
    out = out.resize((W, round(out.size[1] * W / out.size[0])), Image.LANCZOS)
    out = out.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    path = os.path.join(out_dir, "rpt_location.png")
    out.save(path, optimize=True); print("rpt_location", out.size)
    return path
