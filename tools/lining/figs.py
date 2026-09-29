# -*- coding: utf-8 -*-
"""
보고서 삽도 → <프로젝트>/runs/fig/rpt_*.png   (lining.json "figs" 로 태그·문구 지정)

  model   해석모델도(지반스프링·단부 스프링 기호·부재번호)
  loads   하중재하도(자중·이완하중·잔류수압·온도)
  forces  하중조합별 해석결과도 — NX 캡처(runs/cap/<태그>_<조합>_N|V|M.jpg, capture.py) + 변형도
  pm      철근 패턴 P-M 상관도(아치부 + 측벽 최소 안전율 부재)
  sf      검토항목별 안전율 막대(report_data.json)
프로젝트 고유 삽도(설계서 그림 재배치, 표준단면도 WMF 등)는 프로젝트 스크립트에 둔다.
"""
import os, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from . import post as LP
from . import check as C

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
INK, MUTED, GRID = "#222222", "#8a8a8a", "#dddddd"
BLUE, ORANGE, RED = "#1f5fa8", "#c2571a", "#b3261e"
FONT = ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 44)
PALETTE = [("#9aa5b1", "o"), (BLUE, "o"), (ORANGE, "s"), ("#2e8b57", "^"), ("#7b3fa0", "v"), ("#555555", "D")]


def _cfg(prj):
    return prj.cfg.get("figs", {})


def load(prj, tag):
    return LP.load(prj.result_path(tag))


def lining(ax, R, lw=2.0):
    n = R["geom"]["nodes"]
    ax.plot([p[0] for p in n], [p[1] for p in n], color=INK, lw=lw)
    for k, k2 in ((0, 1), (len(n) - 1, len(n) - 2)):
        if R.get("sup") == "spring":            # 단부 스프링: 라이닝 축선 연장 방향 압축전담 스프링 + 지반 고정점
            (x, z), (x2, z2) = n[k], n[k2]
            L = math.hypot(x - x2, z - z2); tx, tz = (x - x2) / L, (z - z2) / L; px, pz = -tz, tx
            t = np.linspace(0.08, 0.62, 11); off = np.array([0, .08, -.08, .08, -.08, .08, -.08, .08, -.08, .08, 0])
            ax.plot([x, x + 0.08 * tx], [z, z + 0.08 * tz], color=RED, lw=1.4)
            ax.plot(x + t * tx + off * px, z + t * tz + off * pz, color=RED, lw=1.4)
            ax.plot([x + 0.62 * tx, x + 0.75 * tx], [z + 0.62 * tz, z + 0.75 * tz], color=RED, lw=1.4)
            gx, gz = x + 0.75 * tx, z + 0.75 * tz
            ax.plot([gx - 0.25 * px, gx + 0.25 * px], [gz - 0.25 * pz, gz + 0.25 * pz], color=RED, lw=2.0)
            for q in np.linspace(-0.22, 0.22, 5):
                ax.plot([gx + q * px, gx + q * px + 0.12 * tx - 0.08 * px], [gz + q * pz, gz + q * pz + 0.12 * tz - 0.08 * pz], color=RED, lw=0.9)
        else:
            ax.plot(*n[k], marker="^", color=INK, ms=8)


def model(prj):
    F = _cfg(prj)
    R = load(prj, F["model_tag"])
    nodes = R["geom"]["nodes"]; nrm = R["geom"]["normals"]
    ne = prj.cfg["geometry"]["n_elem"]; nL, nA, nR = ne["L"], ne["A"], ne["R"]; nt = nL + nA + nR
    labels = F.get("model_labels") or [1, (nL + 1) // 2 + 1, nL, nL + 1, nL + nA // 4 + 1, nL + nA // 2, nL + nA // 2 + 1, nL + 3 * nA // 4 + 1,
                                        nL + nA, nL + nA + 1, nL + nA + nR // 2, nt]
    fig, ax = plt.subplots(figsize=(8.4, 6.2))
    lining(ax, R)
    for i, ((x, z), (nx, nz)) in enumerate(zip(nodes, nrm), start=1):
        ax.plot([x, x + 0.8 * nx], [z, z + 0.8 * nz], color=BLUE, lw=1.0)
        t = np.linspace(0.15, 0.65, 9); off = np.array([0, 0.07, -0.07, 0.07, -0.07, 0.07, -0.07, 0.07, 0])
        px, pz = -nz, nx
        ax.plot(x + t * nx + off * px, z + t * nz + off * pz, color=BLUE, lw=0.9)
        ax.plot(x + 0.8 * nx, z + 0.8 * nz, marker="s", ms=3.5, color=BLUE)
    for e in R["geom"]["elems"]:
        if e["id"] in labels:
            i, j = e["i"] - 1, e["j"] - 1
            mx, mz = (nodes[i][0] + nodes[j][0]) / 2, (nodes[i][1] + nodes[j][1]) / 2
            nx, nz = e["n"]
            ax.text(mx - 0.42 * nx, mz - 0.42 * nz, str(e["id"]), ha="center", va="center", fontsize=8.5, color=INK)
    ax.text(0, 3.4, "도심축 보요소 %d개\n(좌측벽 1~%d · 아치 %d~%d · 우측벽 %d~%d)" % (nt, nL, nL + 1, nL + nA, nL + nA + 1, nt),
            ha="center", fontsize=9.5, color=INK)
    ax.text(0, 1.6, "지반스프링: 절점 법선방향 압축전용 (인장 시 제거)", ha="center", fontsize=9.5, color=BLUE)
    if R.get("sup") == "spring":
        ax.text(0, 0.7, F.get("model_foot_text", "측벽 하단: 라이닝 축선 방향 압축전용 단부 스프링"), ha="center", fontsize=9.5, color=RED)
    ax.set_aspect("equal"); ax.axis("off")
    fig.tight_layout(); fig.savefig(os.path.join(prj.fig, "rpt_model.png"), dpi=200); plt.close(fig)


def loads(prj):
    F = _cfg(prj)
    R = load(prj, F["loads_tag"])
    nodes = R["geom"]["nodes"]
    has_temp = bool(F.get("temp_title"))
    fig, axs = plt.subplots(2, 2, figsize=(12, 9.2))
    axs = axs.ravel()
    titles = ["자중 (프로그램 자동재하)", "이완하중 (라이닝 법선방향, P·cosθ)", "잔류수압 (라이닝 법선방향, Pw·cosθ)", F.get("temp_title", "")]
    for ax, tt in zip(axs, titles):
        lining(ax, R, lw=1.8); ax.set_title(tt, fontsize=13, color=INK); ax.set_aspect("equal"); ax.axis("off")
        ax.set_xlim(-8.6, 8.6); ax.set_ylim(-0.6, 10.2)
    axs[0].annotate("", xy=(0, 3.2), xytext=(0, 5.6), arrowprops=dict(arrowstyle="-|>", color=INK, lw=2.2))
    axs[0].text(0.35, 4.3, "γc = %g kN/m³" % prj.mat["gamma"], fontsize=12)
    for ax, col, lab in ((axs[1], ORANGE, "PV (천단) → 0 (스프링라인)"), (axs[2], BLUE, "Pw = Hw·γw (천단) → 0 (스프링라인)")):
        env = []
        for e in R["geom"]["elems"]:
            nx, nz = e["n"]
            if nz <= 0: continue
            i, j = e["i"] - 1, e["j"] - 1
            mx, mz = (nodes[i][0] + nodes[j][0]) / 2, (nodes[i][1] + nodes[j][1]) / 2
            L = 2.4 * nz
            env.append((mx + L * nx, mz + L * nz))
            if e["id"] % 2 == 0:
                ax.annotate("", xy=(mx + 0.05 * nx, mz + 0.05 * nz), xytext=(mx + L * nx, mz + L * nz), arrowprops=dict(arrowstyle="-|>", color=col, lw=1.2))
        ax.plot([p[0] for p in env], [p[1] for p in env], color=col, lw=1.2)
        ax.text(0, 3.6, lab, ha="center", fontsize=12, color=col)
    if has_temp:
        for e in R["geom"]["elems"][4::7]:
            i, j = e["i"] - 1, e["j"] - 1; nx, nz = e["n"]
            mx, mz = (nodes[i][0] + nodes[j][0]) / 2, (nodes[i][1] + nodes[j][1]) / 2
            axs[3].annotate("", xy=(mx + 1.0 * nx, mz + 1.0 * nz), xytext=(mx - 0.8 * nx, mz - 0.8 * nz), arrowprops=dict(arrowstyle="<|-|>", color=RED, lw=1.4))
        axs[3].text(0, 3.4, F.get("temp_text", ""), ha="center", fontsize=12, color=RED)
    fig.tight_layout(); fig.savefig(os.path.join(prj.fig, "rpt_loads.png"), dpi=170); plt.close(fig)


def _crop_cap(path, bg_px=(5, 1200), legend_w=138, legend_h=900, left_skip=200):
    """NX 캡처(2400×1500) → 부재력도 부분과 범례. 배경색 bg_px 에서 40 이상 다른 픽셀을 내용으로 본다."""
    im = Image.open(path).convert("RGB"); a = np.array(im).astype(int)
    bg = a[bg_px]
    diff = np.abs(a - bg).sum(axis=2) > 40
    sub = diff[:, left_skip:]; xs = np.nonzero(sub.any(axis=0))[0] + left_skip; ys = np.nonzero(sub.any(axis=1))[0]
    arch = im.crop((xs.min() - 30, ys.min() - 30, xs.max() + 30, ys.max() + 30))
    leg_rows = np.nonzero(diff[:legend_h, :legend_w].any(axis=1))[0]
    legend = im.crop((0, 0, legend_w, min(legend_h, leg_rows.max() + 10))) if len(leg_rows) else None

    def whiten(x):
        b = np.array(x).astype(int); m = (np.abs(b - bg).sum(axis=2) <= 12); b[m] = 255; return Image.fromarray(b.astype(np.uint8))
    return whiten(arch), (whiten(legend) if legend is not None else None)


def _deform_png(R, lc, path):
    n = R["geom"]["nodes"]; D = R["DP"][lc]
    dmax = max(math.hypot(*D[i + 1]) for i in range(len(n)))
    s = 0.9 / dmax
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.plot([p[0] for p in n], [p[1] for p in n], color=MUTED, lw=1.2, ls="--", label="변형 전")
    ax.plot([p[0] + s * D[i + 1][0] for i, p in enumerate(n)], [p[1] + s * D[i + 1][1] for i, p in enumerate(n)], color=BLUE, lw=2, label="변형 후")
    z = min(D.items(), key=lambda kv: kv[1][1]); x = max(D.items(), key=lambda kv: abs(kv[1][0]))
    ax.text(0, 8.1, "천단 연직변위 %.2f mm (절점 %d)" % (z[1][1] * 1000, z[0]), ha="center", fontsize=12)
    ax.text(0, 7.4, "최대 수평변위 %.2f mm (절점 %d)" % (x[1][0] * 1000, x[0]), ha="center", fontsize=12)
    ax.set_aspect("equal"); ax.axis("off"); ax.legend(loc="lower center", fontsize=10, frameon=False, ncol=2)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def forces(prj, tag, lc):
    R = load(prj, tag)
    parts = []
    for t, title in (("N", "축력도 (kN)"), ("V", "전단력도 (kN)"), ("M", "휨모멘트도 (kN·m)")):
        arch, leg = _crop_cap(os.path.join(prj.cap, "%s_%s_%s.jpg" % (tag, lc, t)))
        parts.append((title, arch, leg))
    dp = os.path.join(prj.fig, "_def_%s_%s.png" % (tag, lc)); _deform_png(R, lc, dp)
    parts.append(("변형도 (확대)", Image.open(dp).convert("RGB"), None))
    cw, chh = 1500, 900
    sheet = Image.new("RGB", (cw * 2, (chh + 80) * 2), "white"); dr = ImageDraw.Draw(sheet)
    for k, (title, im, leg) in enumerate(parts):
        x0 = (k % 2) * cw; y0 = (k // 2) * (chh + 80)
        dr.text((x0 + cw // 2, y0 + 30), title, fill=(34, 34, 34), font=FONT, anchor="mm")
        area_w = cw - (230 if leg is not None else 40)
        sc = min(area_w / im.size[0], (chh - 20) / im.size[1])
        r = im.resize((int(im.size[0] * sc), int(im.size[1] * sc)), Image.LANCZOS)
        sheet.paste(r, (x0 + (230 if leg is not None else 20), y0 + 80 + (chh - r.size[1]) // 2))
        if leg is not None:
            ls = min(210 / leg.size[0], (chh - 40) / leg.size[1], 1.6)
            lr = leg.resize((int(leg.size[0] * ls), int(leg.size[1] * ls)), Image.LANCZOS)
            sheet.paste(lr, (x0 + 10, y0 + 90))
    dr.line([(cw, 0), (cw, sheet.size[1])], fill=(200, 200, 200), width=2)
    dr.line([(0, chh + 80), (sheet.size[0], chh + 80)], fill=(200, 200, 200), width=2)
    out = os.path.join(prj.fig, "rpt_forces_%s_%s.png" % (tag, lc))
    sheet.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(out, optimize=True)   # 256색(용량 1/3)
    print("forces", out, sheet.size)


def forces_all(prj):
    for tag in prj.cfg["report"]["main"]:
        R = json.load(open(prj.result_path(tag), encoding="utf-8"))
        roles = prj.combo_roles[prj.patterns[R["sec"]]["combos"]]
        for lc, _ in R["combos"]:
            if roles.get(lc) in ("strength", "service"):
                forces(prj, tag, lc)


def pm_curve(h_m, fck):
    h = h_m * 1000
    Ag = h * 1000; Pn0 = 0.85 * fck * (Ag - 2 * C.AS) + C.FY * 2 * C.AS; cap = 0.80 * 0.65 * Pn0
    pts = []
    for c in np.concatenate([np.linspace(8, h, 160), np.linspace(h, 6 * h, 60)]):
        P, M, et = C._state(c, h, fck); ph = C._phi(et)
        pts.append((ph * M / 1e6, min(ph * P, cap) / 1e3))
    return pts


def pm(prj, tag=None, out_name=None, title=None):
    F = _cfg(prj)
    tag = tag or F["pm_tag"]
    fk = "%g" % prj.fck
    res = C.check_run(prj, tag, fcks=(prj.fck,))
    STR = prj.roles(res["sec"], "strength")
    arch_t = prj.cfg.get("report", {}).get("arch_t", 0.300)
    wall = max((r for lc in STR for r in res["cases"][lc]["rows"] if r["reg"] in ("L", "R")), key=lambda r: r[fk]["pm"])
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.6))
    for ax, (h, regs, ttl) in zip(axs, ((arch_t, ("A",), "아치부 (h = %.0f mm)" % (arch_t * 1000)),
                                        (wall["h"], ("L", "R"), "측벽부 (최소 안전율 부재 %s, h = %.0f mm)" % (wall["elem"], wall["h"] * 1000)))):
        cv = pm_curve(h, prj.fck)
        ax.plot([p[0] for p in cv], [p[1] for p in cv], color=INK, lw=2, label="설계강도 φMn–φPn")
        for (lc, (col, mk)) in zip(STR, PALETTE):
            rows = [r for r in res["cases"][lc]["rows"] if r["reg"] in regs and (abs(r["h"] - h) < 0.002 or regs == ("A",))]
            ax.scatter([abs(r["M"]) for r in rows], [r["N"] for r in rows], s=14, color=col, marker=mk, label="Comb.%s" % lc[1:], zorder=3)
        gov = max((r for lc in STR for r in res["cases"][lc]["rows"] if r["reg"] in regs and (abs(r["h"] - h) < 0.002 or regs == ("A",))),
                  key=lambda r: r[fk]["pm"])
        ax.annotate("SF = %.2f" % (1 / gov[fk]["pm"]), xy=(abs(gov["M"]), gov["N"]), xytext=(abs(gov["M"]) + 40, gov["N"] + 900),
                    arrowprops=dict(arrowstyle="->", color=RED), color=RED, fontsize=11)
        ax.set_xlim(0, None); ax.set_ylim(0, None)
        ax.set_xlabel("휨모멘트 M (kN·m)"); ax.set_ylabel("축력 P (kN)"); ax.set_title(ttl, fontsize=11)
        ax.grid(color=GRID, lw=0.6)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.legend(fontsize=8.5, frameon=False, loc="upper right")
    fig.suptitle(title or F.get("pm_title", "%s 철근콘크리트 라이닝 P-M 상관도" % res["sec"]), fontsize=12)
    fig.tight_layout(); fig.savefig(os.path.join(prj.fig, out_name or F.get("pm_out", "rpt_pm_%s.png" % res["sec"].replace("-", ""))), dpi=180); plt.close(fig)


def sf(prj):
    D = json.load(open(os.path.join(prj.runs, "report_data.json"), encoding="utf-8"))["sections"]
    rows = []
    for tag in prj.cfg["report"]["main"]:
        S = D[tag]; key = "comp" if S["type"] == "무근" else "pm"
        for grp in ("아치", "측벽"):
            for k, lab in ((key, "휨·압축"), ("shear", "전단")):
                rows.append(("%s %s %s" % (S["sec"], grp, lab), S["checks"]["%s|%s" % (grp, k)]["SF"]))
    fig, ax = plt.subplots(figsize=(9, 8.2))
    y = list(range(len(rows)))[::-1]
    for x0, x1, col, lab in ((0.6, 0.75, "#f4d6d3", "E"), (0.75, 0.90, "#f8e3cc", "D"), (0.90, 1.0, "#fbf0cf", "C")):
        ax.axvspan(x0, x1, color=col, lw=0, zorder=0); ax.text((x0 + x1) / 2, len(rows) - 0.4, lab, ha="center", fontsize=9, color="#7a4a1a")
    ax.text(1.05, len(rows) - 0.4, "A / B", fontsize=9)
    ax.barh(y, [r[1] for r in rows], height=0.55, color=BLUE, zorder=2)
    for v, r in zip(y, rows):
        ax.text(r[1] + 0.03, v, "%.2f" % r[1], va="center", fontsize=9)
    ax.axvline(1.0, color=RED, lw=1.2, zorder=3)
    ax.set_xlim(0.6, max(r[1] for r in rows) * 1.12); ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=9.5)
    ax.set_xlabel(_cfg(prj).get("sf_xlabel", "안전율 SF = 설계강도 / 소요강도"))      # 강도 등 판단 사항은 그림 아래 주석으로
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(os.path.join(prj.fig, "rpt_sf.png"), dpi=180); plt.close(fig)


def all_figs(prj, which=("model", "loads", "forces", "pm", "sf")):
    os.makedirs(prj.fig, exist_ok=True)
    C.configure(prj)
    for w in which:
        {"model": model, "loads": loads, "forces": forces_all, "pm": pm, "sf": sf}[w](prj)
