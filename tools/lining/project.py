# -*- coding: utf-8 -*-
"""
프로젝트 입력(`<프로젝트>/lining.json`) 읽기와 파생값 계산.

원칙(9/18 sources.py 의 뜻을 잇는다): 값마다 출처(`src`)를 적고, 채우지 않은 값은 "(확인 필요)"로 둔다.
"(확인 필요)"가 하나라도 남아 있으면 해석·검토 명령은 멈춘다(`Project.require()`).

파생값
  Ks  : 주어지지 않으면 Es / ((1+ν)·R_eq), R_eq = √(A_design/π)  (AFTES·미공병단 지반공동이론식) — 소수 0자리 반올림
  PV  : 주어지지 않으면 이완하중고 Hp, 단위중량 γt, 잔류수압 수위 Hw 로
        Hp > Hw : (Hp − Hw)·γt + Hw·(γt − γw),  Hp ≤ Hw : Hp·(γt − γw)   (설계서 P-4·P-5 식과 같은 방법) — 소수 3자리
  Pw  : 주어지지 않으면 Hw·γw — 소수 2자리
"""
import json, os, math

TODO = "(확인 필요)"


def _find_todo(o, path=""):
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k.startswith("_"): continue          # _설명 등 주석 키
            out += _find_todo(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out += _find_todo(v, "%s[%d]" % (path, i))
    elif isinstance(o, str) and TODO in o:
        out.append(path)
    return out


class Project:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.cfg_path = os.path.join(self.root, "lining.json")
        self.cfg = json.load(open(self.cfg_path, encoding="utf-8"))
        c = self.cfg
        self.name = c.get("name", os.path.basename(self.root))
        p = c.get("paths", {})
        self.runs = os.path.join(self.root, p.get("runs", "runs"))
        self.cap = os.path.join(self.root, p.get("cap", "runs/cap"))
        self.fig = os.path.join(self.root, p.get("fig", "runs/fig"))
        self.mat = c["material"]
        fck = self.mat.get("fck")
        self.fck = float(fck) if isinstance(fck, (int, float)) else None     # (확인 필요)면 None — require() 가 막는다
        m = c.get("model", {})
        self.link_len = m.get("link_len", 1.0)
        self.gnd0 = m.get("gnd0", 100)
        self.spring_dir = m.get("spring_dir", "radial")
        self.gamma_w = m.get("gamma_w", 10.0)
        a = c.get("A_design")
        self.R_eq = math.sqrt(a / math.pi) if isinstance(a, (int, float)) else None
        self.foot = c.get("foot", {})
        self.combo_sets = {k: [(n, dict(f)) for n, f, *_ in v] for k, v in c["combos"].items() if not k.startswith("_")}
        self.combo_roles = {k: {n: (r[0] if r else "strength") for n, f, *r in v} for k, v in c["combos"].items() if not k.startswith("_")}
        self.patterns = {k: self._pattern(k, v) for k, v in c["patterns"].items() if not k.startswith("_")}
        self.check = c.get("check", {})
        self.runs_cfg = {r["tag"]: r for r in c.get("runs", [])}

    # ── 파생값 ──
    def _pattern(self, name, v):
        s = dict(v)
        if s.get("Ks") is None and all(isinstance(s.get(k), (int, float)) for k in ("Es", "nu")) and self.R_eq:
            s["Ks"] = round(s["Es"] / ((1 + s["nu"]) * self.R_eq), 0)
        if s.get("PV") is None and all(isinstance(s.get(k), (int, float)) for k in ("Hp", "gamma_t", "Hw")):
            Hp, gt, Hw, gw = s["Hp"], s["gamma_t"], s["Hw"], self.gamma_w
            s["PV"] = round((Hp - Hw) * gt + Hw * (gt - gw) if Hp > Hw else Hp * (gt - gw), 3)
        if s.get("Pw") is None and isinstance(s.get("Hw"), (int, float)):
            s["Pw"] = round(s["Hw"] * self.gamma_w, 2)
        s.setdefault("temp", False)
        s.setdefault("rc", False)
        s.setdefault("combos", "temp" if s["temp"] else "plain")
        return s

    def sect(self, pat):
        """해석에 쓰는 패턴 값(결과 JSON 의 "S" 로 저장된다)."""
        s = self.patterns[pat]
        keep = ("Ks", "PV", "Pw", "temp", "src", "E0")
        return {k: s[k] for k in keep if k in s}

    def combos(self, pat):
        s = self.patterns[pat]
        if isinstance(s["combos"], list):
            return [(n, dict(f)) for n, f, *_ in s["combos"]]
        return self.combo_sets[s["combos"]]

    def roles(self, pat, role):
        s = self.patterns[pat]
        return [n for n, r in self.combo_roles[s["combos"]].items() if r == role]

    def rc_patterns(self):
        return {k for k, v in self.patterns.items() if v.get("rc")}

    # ── 점검 ──
    def unresolved(self):
        return _find_todo(self.cfg)

    def require(self):
        todo = self.unresolved()
        if todo:
            raise SystemExit("lining.json 에 %s 항목 %d개 — 채우기 전에는 해석하지 않는다:\n  %s" % (TODO, len(todo), "\n  ".join(todo[:40])))

    def path(self, rel):
        return rel if os.path.isabs(rel) else os.path.join(self.root, rel)

    def result_path(self, tag):
        return os.path.join(self.runs, tag + "_result.json")


def load(root):
    return Project(root)
