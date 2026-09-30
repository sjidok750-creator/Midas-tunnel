# -*- coding: utf-8 -*-
"""
터널 라이닝 해석 엔진 — 명령줄

  cd D:\\Midas-tunnel\\tools
  python -m lining new <터널명>                    # projects/<터널명>/ 와 lining.json 틀((확인 필요) 자리표시)
  python -m lining status <프로젝트>              # (확인 필요) 남은 항목, 해석 태그 목록
  python -m lining geom <프로젝트>                # 단면 형상 점검(설계 B·Ht·A·R 과 대조)
  python -m lining selftest <프로젝트>            # 검토식 역검산(설계 구조계산서 값)
  python -m lining mct <프로젝트> [태그…]          # MCT 만 작성(MIDAS 불필요 — 회귀 점검용)
  python -m lining run <프로젝트> [태그…]          # MIDAS 해석(태그 없으면 lining.json "runs" 전부)
  python -m lining capture <프로젝트> [태그…]      # NX 캡처(없으면 report.main 전부)
  python -m lining data <프로젝트>                # runs/report_data.json
  python -m lining figs <프로젝트> [model loads forces pm sf]
  python -m lining location <프로젝트>            # 검토 위치도(실제 도면 위 표기)
  python -m lining umd <프로젝트> <태그> [부재…]   # midas UMD(RC/Wall) 계수하중 표(붙여넣기 TSV)·단면 설정값
<프로젝트> 는 폴더 경로 또는 projects/ 아래 이름.
"""
import sys, os, json, shutil
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
if HERE not in sys.path:
    pass
from . import project as P


def _prj(arg):
    p = arg if os.path.isdir(arg) else os.path.join(REPO, "projects", arg)
    return P.load(p)


def cmd_new(name):
    root = os.path.join(REPO, "projects", name)
    if os.path.exists(os.path.join(root, "lining.json")):
        raise SystemExit("이미 있음: %s" % root)
    os.makedirs(os.path.join(root, "runs"), exist_ok=True)
    os.makedirs(os.path.join(root, "report", "_template"), exist_ok=True)
    tpl = json.load(open(os.path.join(HERE, "lining_template.json"), encoding="utf-8"))
    tpl["name"] = name
    json.dump(tpl, open(os.path.join(root, "lining.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(root, "README.md"), "w", encoding="utf-8").write(
        "# %s — 라이닝 안전성평가\n\n자료 위치, 대표님 결정(강도·제외 구간·평가 기준 하중형상·설계 비교), 진행 기록을 여기에 쓴다.\n"
        "절차: tunnel-lining 스킬. 입력: lining.json ((확인 필요)를 모두 채운 뒤 해석).\n" % name)
    print("만듦:", root)
    print("다음: lining.json 의 (확인 필요) 채우기 → python -m lining status", name)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__); return
    cmd, rest = argv[0], argv[1:]
    if cmd == "new":
        return cmd_new(rest[0])
    prj = _prj(rest[0]); tags = rest[1:]
    if cmd == "status":
        todo = prj.unresolved()
        print("%s — (확인 필요) %d개" % (prj.name, len(todo)))
        for t in todo: print("  ", t)
        print("해석 태그:", ", ".join(prj.runs_cfg))
        for k, v in prj.patterns.items():
            print("  %-6s Ks %-10s PV %-8s Pw %-6s E0 %-10s %s%s" % (k, v.get("Ks"), v.get("PV"), v.get("Pw"), v.get("E0"),
                                                                  "철근" if v.get("rc") else "무근", " 온도" if v.get("temp") else ""))
        return
    if cmd == "geom":
        from . import geom
        return geom.report(prj)
    if cmd == "selftest":
        from . import check
        check.configure(prj); return check.selftest(prj)
    if cmd == "mct":                                     # 기존 결과를 건드리지 않게 runs/_mct_check/ 에 쓴다
        from . import model
        out = os.path.join(prj.runs, "_mct_check")
        for t in (tags or list(prj.runs_cfg)):
            model.run_tag(prj, t, write_only=True, runs_dir=out)
        print("MCT →", out)
        return
    prj.require()
    if cmd == "run":
        from . import model
        for t in (tags or list(prj.runs_cfg)):
            model.run_tag(prj, t)
    elif cmd == "capture":
        from . import capture
        for t in (tags or prj.cfg["report"]["main"]):
            capture.capture(prj, t)
    elif cmd == "data":
        from . import data
        data.build(prj)
    elif cmd == "figs":
        from . import figs
        figs.all_figs(prj, tuple(tags) if tags else ("model", "loads", "forces", "pm", "sf"))
    elif cmd == "location":
        from . import location
        location.make(prj)
    elif cmd == "umd":
        from . import umd
        umd.make(prj, tags[0], [int(x) for x in tags[1:]])
    else:
        raise SystemExit("모르는 명령: %s\n%s" % (cmd, __doc__))


if __name__ == "__main__":
    main(sys.argv[1:])
