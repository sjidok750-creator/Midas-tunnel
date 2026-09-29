# -*- coding: utf-8 -*-
"""
터널 라이닝 3심원 단면 → 빔-스프링 모델 격자(절점·요소·두께·스프링 방향).

순수 기하다. 기준값(스프링계수·이완하중·허용응력)은 하나도 쓰지 않으므로
계획서 §5의 "원문 확보 전 계산기 금지"에 걸리지 않는다. 그 값들은 sources.py 가 막는다.

좌표계: 원점은 내공 중심선 상의 도면 기준점, x=우(+), y=상(+). 단위 m.
각도 θ: 천단 12시를 0° 로 두고 시계방향(우측 → 인버트 → 좌측)으로 잰다.

3심원(three-centered arch)
  R1 천단부(상부 아치), R2 측벽부(어깨), R3 인버트/바닥.
  각 원의 중심이 다르며, 접점에서 접선이 연속이도록 중심을 배치한다.
  설계사마다 중심 표기 방식이 달라 판독기 규칙은 손볼 수 있다(계획서 §5).
"""
import json
import math


# ─────────────────────────────────────────────────────────────────────
# 원호 정의
# ─────────────────────────────────────────────────────────────────────

class Arc:
    """중심 (cx, cy), 반경 R, 시작각~끝각(도). 각은 위 정의(천단 0°, 시계방향)."""

    def __init__(self, name, cx, cy, R, a0, a1):
        self.name, self.cx, self.cy, self.R = name, cx, cy, R
        self.a0, self.a1 = float(a0), float(a1)

    def point(self, deg):
        """θ(도) 위치의 내공선 좌표. 천단 0°, 시계방향."""
        t = math.radians(deg)
        return (self.cx + self.R * math.sin(t),
                self.cy + self.R * math.cos(t))

    def normal(self, deg):
        """바깥(지반쪽) 단위법선. 중심에서 점을 향하는 방향."""
        t = math.radians(deg)
        return (math.sin(t), math.cos(t))

    def __repr__(self):
        return "<Arc %s R=%.3f c=(%.3f,%.3f) %.1f°~%.1f°>" % (
            self.name, self.R, self.cx, self.cy, self.a0, self.a1)


def 표준_3심원(R1, R2, R3, c1=(0.0, 0.0), c2=None, c3=None,
             θ_R1R2=60.0, θ_R2R3=120.0):
    """
    3심원 구성. 좌우 대칭이므로 원호는 **5개**다: R1(천단) + R2 좌·우(어깨)
    + R3 좌·우(인버트). 한쪽만 만들면 반대쪽 측벽이 직선 현으로 눌린다
    (2026-09-18: -60°~240° 300° 짜리를 폐합해 좌측 벽이 사라졌었다).

    θ_R1R2  천단 원호가 끝나고 어깨 원호가 시작하는 각(도, 우측 기준)
    θ_R2R3  어깨가 끝나고 인버트가 시작하는 각

    각 배치(천단 0°, 시계방향, -180°~180°):
        R1   -θ_R1R2 ~ +θ_R1R2
        R2우  +θ_R1R2 ~ +θ_R2R3        R2좌  -θ_R2R3 ~ -θ_R1R2
        R3우  +θ_R2R3 ~ 180°           R3좌  -180°   ~ -θ_R2R3

    접선 연속: 두 원의 접점에서 중심-접점 방향이 같으므로 두 중심은
    접점을 지나는 한 직선 위에 있다 → c2 = c1 + (R1-R2)·n(접점각).
    도면에 중심 좌표가 있으면 추정하지 말고 그 값을 쓴다.
    """
    c1 = tuple(map(float, c1))
    a1 = Arc("R1", c1[0], c1[1], R1, -θ_R1R2, θ_R1R2)

    if c2 is None:
        n = a1.normal(θ_R1R2)
        c2 = (c1[0] + (R1 - R2) * n[0], c1[1] + (R1 - R2) * n[1])
    c2 = tuple(map(float, c2))
    a2r = Arc("R2우", c2[0], c2[1], R2, θ_R1R2, θ_R2R3)

    if c3 is None:
        n = a2r.normal(θ_R2R3)
        c3 = (c2[0] + (R2 - R3) * n[0], c2[1] + (R2 - R3) * n[1])
    c3 = tuple(map(float, c3))
    a3r = Arc("R3우", c3[0], c3[1], R3, θ_R2R3, 180.0)

    # 좌측은 y축 대칭(x 부호 반전)
    a2l = Arc("R2좌", -c2[0], c2[1], R2, -θ_R2R3, -θ_R1R2)
    a3l = Arc("R3좌", -c3[0], c3[1], R3, -180.0, -θ_R2R3)

    return [a3l, a2l, a1, a2r, a3r]      # 각도 오름차순


def 폐합_R3(R1, R2, θ_R1R2=60.0, θ_R2R3=120.0):
    """
    인버트가 중심선에서 매끄럽게 닫히는 R3.

    좌우 대칭이려면 R3 중심이 y축 위(cx=0)에 있어야 한다:
        c2x = (R1 - R2)·sin θ1
        c3x = c2x + (R2 - R3)·sin θ2 = 0
        →  R3 = R2 + c2x / sin θ2
    도면 R3 가 이 값과 많이 다르면 접점각(θ1·θ2)을 잘못 읽은 것이다.
    """
    c2x = (R1 - R2) * math.sin(math.radians(θ_R1R2))
    return R2 + c2x / math.sin(math.radians(θ_R2R3))


# ─────────────────────────────────────────────────────────────────────
# 두께 t(θ)
# ─────────────────────────────────────────────────────────────────────

def 두께함수(구간):
    """
    구간: [(θ0, θ1, t), ...] — θ0 이상 θ1 미만에서 두께 t(m).
    진단에서는 GPR 실측 두께를 구간별로 넣는다(변단면이 아니라 구간별 단면).

    각은 부호를 그대로 둔다. %360 으로 접으면 천단 좌측(-57.5°)이 302.5° 가 되어
    어느 구간에도 안 걸리고 마지막 구간 두께로 새어나간다(2026-09-18 실측: 천단
    12개 요소가 측벽 두께 0.46 으로 잘못 잡혔다). 구간 밖이면 조용히 넘기지 않고 예외.
    """
    구간 = sorted(구간, key=lambda s: s[0])

    def t(deg):
        d = float(deg)
        for a0, a1, tv in 구간:
            if a0 <= d < a1:
                return tv
        if abs(d - 구간[-1][1]) < 1e-9:      # 마지막 구간 끝점은 포함
            return 구간[-1][2]
        raise ValueError(
            "θ=%.3f° 가 두께 구간 밖이다(%.1f°~%.1f°). "
            "기본값으로 넘기지 않는다 — 구간 정의를 고칠 것."
            % (d, 구간[0][0], 구간[-1][1]))
    t.구간 = 구간
    return t


# ─────────────────────────────────────────────────────────────────────
# 격자 생성
# ─────────────────────────────────────────────────────────────────────

def 격자(arcs, t_func, 간격=5.0, 인버트=True, 시작절점=1, 시작요소=1):
    """
    아치를 `간격`(도)마다 분할해 절점·요소를 만든다.

    반환 dict:
      nodes  {id: (x, y, 0.0)}            NX 는 3D 이므로 z=0 평면 프레임
      elems  [(id, n1, n2, θ중점, t, ℓ)]  요소별 두께·길이
      정보    {절점수, 요소수, 총연장, 폐합여부}

    인버트가 있으면 마지막 절점을 첫 절점에 이어 폐합한다.
    없으면 측벽 하단에서 끊고, 그 절점은 기초(고정 또는 스프링)로 잡는다.
    """
    θ0 = min(a.a0 for a in arcs)
    θ1 = max(a.a1 for a in arcs)

    def arc_at(deg):
        for a in arcs:
            if a.a0 <= deg <= a.a1:
                return a
        return min(arcs, key=lambda a: min(abs(deg - a.a0), abs(deg - a.a1)))

    # 각 원호 경계는 반드시 절점으로 찍는다(꺾임점을 요소 내부에 두지 않는다)
    각들 = set()
    for a in arcs:
        각들.add(a.a0)
        각들.add(a.a1)
        n = max(1, int(round((a.a1 - a.a0) / 간격)))
        for i in range(n + 1):
            각들.add(a.a0 + (a.a1 - a.a0) * i / n)
    각열 = sorted(x for x in 각들 if θ0 - 1e-9 <= x <= θ1 + 1e-9)
    # 360° 폐합이면 -180° 와 +180° 는 같은 점이다. 끝점을 빼고 요소로 잇는다.
    if 인버트 and abs((θ1 - θ0) - 360.0) <= 1e-6:
        각열 = [x for x in 각열 if x < θ1 - 1e-9]

    nodes, 각_of = {}, {}
    nid = 시작절점
    for d in 각열:
        x, y = arc_at(d).point(d)
        nodes[nid] = (round(x, 6), round(y, 6), 0.0)
        각_of[nid] = d
        nid += 1

    ids = sorted(nodes)
    쌍 = list(zip(ids[:-1], ids[1:]))
    폐합 = False
    if 인버트:
        # 폐합은 원호가 360° 를 다 덮을 때만 뜻이 있다. 덜 덮은 채로 이으면
        # 빠진 구간이 직선 현으로 눌려 벽이 통째로 사라진다.
        if abs((θ1 - θ0) - 360.0) > 1e-6:
            raise ValueError(
                "원호가 %.1f° 만 덮는다(360° 필요). 인버트로 폐합하려면 좌우 원호를 "
                "모두 넣어야 한다 — 빠진 구간이 직선이 되어 버린다." % (θ1 - θ0))
        # 각도만 보고 닫으면 안 된다. 좌우 끝점이 실제로 같은 자리에 와야 한다.
        # R 조합이 맞지 않으면 인버트가 중심선을 지나쳐 좌우가 교차한다.
        (x가, y가, _), (x나, y나, _) = nodes[ids[0]], nodes[ids[-1]]
        간극 = math.hypot(x나 - x가, y나 - y가)
        예상 = 2.0 * math.pi * max(a.R for a in arcs) * (간격 / 360.0)
        if 간극 > max(3.0 * 예상, 0.05):
            raise ValueError(
                "인버트가 닫히지 않는다: 양 끝이 (%.3f, %.3f) 와 (%.3f, %.3f) 로 %.3f m 떨어져 있다.\n"
                "  R1·R2·R3 조합이나 접점각이 도면과 다르다 — 표준단면도 값을 확인할 것."
                % (x가, y가, x나, y나, 간극))
        쌍.append((ids[-1], ids[0]))      # 마지막 절점 → 첫 절점
        폐합 = True

    elems, eid, 총 = [], 시작요소, 0.0
    for (n1, n2) in 쌍:
        (x1, y1, _), (x2, y2, _) = nodes[n1], nodes[n2]
        ℓ = math.hypot(x2 - x1, y2 - y1)
        d1, d2 = 각_of[n1], 각_of[n2]
        θm = (d1 + d2) / 2.0 if n2 != ids[0] else ((d1 + d2 + 360.0) / 2.0) % 360.0
        elems.append((eid, n1, n2, round(θm, 3), round(t_func(θm), 4), round(ℓ, 6)))
        총 += ℓ
        eid += 1

    return {
        "nodes": nodes,
        "elems": elems,
        "각": 각_of,
        "정보": {"절점수": len(nodes), "요소수": len(elems),
                "총연장_m": round(총, 4), "폐합": 폐합},
    }


def 스프링방향(arcs, 각_of):
    """
    절점별 반경방향 단위벡터(바깥 = 지반쪽).
    지반스프링은 이 방향의 압축만 받는다. 스프링 상수는 여기서 계산하지 않는다
    — sources.py 의 근거 등록을 거쳐야 한다.
    """
    def arc_at(deg):
        for a in arcs:
            if a.a0 <= deg <= a.a1:
                return a
        return arcs[0]

    out = {}
    for nid, d in 각_of.items():
        nx, ny = arc_at(d).normal(d)
        out[nid] = (round(nx, 6), round(ny, 6))
    return out


def 단면상수(t, b=1.0):
    """단위폭 b 의 직사각 단면. A, I, Z."""
    return {"A": round(b * t, 6),
            "I": round(b * t ** 3 / 12.0, 9),
            "Z": round(b * t ** 2 / 6.0, 9)}


def 자중(elems, γ, b=1.0):
    """라이닝 자중 합계 [kN]. NX DEAD 반력 합과 대조하는 검증값."""
    return round(sum(t * b * ℓ * γ for (_, _, _, _, t, ℓ) in elems), 4)


def 저장(경로, 격자결과, arcs, 스프링, 메타=None):
    d = {
        "메타": 메타 or {},
        "원호": [{"name": a.name, "cx": a.cx, "cy": a.cy, "R": a.R,
                 "a0": a.a0, "a1": a.a1} for a in arcs],
        "절점": {str(k): v for k, v in 격자결과["nodes"].items()},
        "요소": [{"id": e, "n1": n1, "n2": n2, "θ": θ, "t": t, "L": ℓ}
                for (e, n1, n2, θ, t, ℓ) in 격자결과["elems"]],
        "스프링방향": {str(k): v for k, v in 스프링.items()},
        "정보": 격자결과["정보"],
    }
    with open(경로, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return 경로


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # 시험 구동: 읍애터널 제원(B=12.872, Ht=7.960, 아치 t=0.30, 측벽 t=0.46).
    # R1·R2·R3 는 아직 도면에서 읽지 않았다 → 임의값. 실제 값은 표준단면도 판독 후.
    R1, R2 = 6.436, 4.0
    R3 = 폐합_R3(R1, R2)
    arcs = 표준_3심원(R1=R1, R2=R2, R3=R3)
    t = 두께함수([(-180, -60, 0.46), (-60, 60, 0.30), (60, 180, 0.46)])
    g = 격자(arcs, t, 간격=5.0, 인버트=True)
    sp = 스프링방향(arcs, g["각"])

    print("원호:", *arcs, sep="\n  ")
    print("\n격자:", g["정보"])

    # 두께 배분 확인 — 음의 각이 측벽으로 새지 않는지
    n천단 = sum(1 for e in g["elems"] if abs(e[3]) < 60)
    n천단_t = sum(1 for e in g["elems"] if abs(e[3]) < 60 and e[4] == 0.30)
    print("천단부(|θ|<60°) 요소 %d개 중 t=0.30 인 것 %d개" % (n천단, n천단_t))

    # 좌우 대칭 확인 — 좌측 벽이 직선으로 눌리지 않았는지
    xs = [v[0] for v in g["nodes"].values()]
    print("x 범위: %.3f ~ %.3f (좌우 대칭이면 절댓값이 비슷)" % (min(xs), max(xs)))

    print("\n아치 단면상수 t=0.30:", 단면상수(0.30))
    print("측벽 단면상수 t=0.46:", 단면상수(0.46))
    print("자중(γ=23.5): %.4f kN/m" % 자중(g["elems"], 23.5))
    print("\n※ R1·R2·R3 는 시험용 임의값이다. 표준단면도 판독 후 교체할 것.")
