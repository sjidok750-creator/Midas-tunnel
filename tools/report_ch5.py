# -*- coding: utf-8 -*-
"""
보고서 장(hwpx) 조립 도우미 — 양식 hwpx 의 문단·표·그림·수식 개체를 복제해 내용만 바꾼다(한글 편집 지침 v2~v3.4).

  from report_ch5 import B, ro, jo, scrub_package, finish, replace_text_everywhere, TMAP_TEMPLATE1
  doc = Hwpx(양식); doc.load(); ps = doc.paragraphs()
  b = B(doc, ps)            # 양식 문단 번호(tmap)는 양식마다 다르다 — TMAP_TEMPLATE1 은 실증에 쓴 터널 5장 양식 기준
  b.anchor = ps[11]         # 이 문단 뒤에 이어 쓴다
  b.h1("개요"); b.tga("…"); b.table("표제목", [[머리행], [행]…], widths=[…], merges=[(r0,c0,r1,c1)], key="loc"); b.fig(png, "그림제목", key="…")
  본문에서 그림·표 참조는 "[그림 §F:키§]", "[표 §T:키§]과" 처럼 쓰면 resolve() 가 번호와 조사(와/과)를 채운다.
  finish(doc, b, OUT, "제5장 …(터널명)", thumb_fix=…)   # 참조 치환·표 주 붙이기·레이아웃·번호·이미지 정리·메타데이터·저장·검증

표: 바깥 0.4 mm, 머리행 아래 이중선 0.5 mm, 안쪽 0.12 mm, 칸 높이 자동(같은 줄 수 같은 높이, 병합 셀 = 걸친 행 합).
쪽 배치(제목·표가 쪽 끝에 홀로 남는지)는 한글 렌더(PDF)로 확인해야 한다 — keepWithNext 는 글자처럼 취급 표에 효과 없음.
"""
import sys, os, copy, re
HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.normpath(os.path.join(HERE, "..", "core", "tools"))
if CORE not in sys.path:
    sys.path.insert(0, CORE)
from hwpx_edit import Hwpx, para_text, P  # noqa: F401
from hwpx_table import (new_table, new_para, insert_after, fix_layout, merge_cells,  # noqa: F401
                        set_table_lines, autosize_table, keep_with_next, commit_header)
from PIL import Image

# 실증에 쓴 터널 5장 양식 hwpx 의 문단 번호 → 복제할 서식(h1 장·h2 절·h3 가.·h4 1)·h5 ①, b* 본문, tcap 표제목, tbl 표, fig·figcap 그림, eq 수식)
TMAP_TEMPLATE1 = dict(h1=12, h2=13, h3=14, h4=49, h5=52, b11=40, bga=15, b1=109, b5=264, note=29, tcap=27, tbl=313, flow=18, flowcap=19,
                      fig=227, figcap=228, sp=20, eq=251, eqt=265, crit=28)


def ro(s):
    """숫자 문자열 뒤 조사 '으로/로' (끝자리 읽기: 0 영·3 삼·6 육 → 으로)"""
    return s + ("으로" if s[-1] in "036" else "로")


def jo(num):
    """괄호가 뒤따를 때 — 숫자 끝자리로 고른 조사만 돌려준다"""
    return "으로" if num[-1] in "036" else "로"


def scrub_package(doc, title, thumb_fix=None):
    """양식 패키지에서 따라온 미리보기·메타데이터를 새 문서 것으로 교체.
    Preview/PrvText.txt(첫 쪽 본문), content.hpf(제목·작성자·날짜), zip 항목 시각. 표지 썸네일(Preview/PrvImage.png)은
    양식마다 달라 thumb_fix(doc) 콜백으로 고친다(없으면 그대로)."""
    import io, datetime
    # 1) 미리보기 텍스트 — 새 본문 앞부분(표는 <…>)
    lines, k = [], 0
    for p in doc.paragraphs():
        tbl = next(p.iter(P + "tbl"), None)
        if tbl is not None:
            cells = [para_text(q) for q in tbl.iter(P + "p")]
            t = "<" + " ".join(c for c in cells if c.strip()) + ">"
        else:
            t = para_text(p)
        lines.append(t); k += len(t)
        if k > 1000: break
    doc.data["Preview/PrvText.txt"] = ("\r\n" + "\r\n".join(lines))[:1024].encode("utf-8")
    thumb = thumb_fix(doc) if thumb_fix else {}
    # 3) content.hpf 메타데이터 — 예제 작성자·작성일 제거
    now = datetime.datetime.now()
    utc = now.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ampm = "오전" if now.hour < 12 else "오후"
    kdate = f"{now.year}년 {now.month}월 {now.day}일 {'월화수목금토일'[now.weekday()]}요일 {ampm} {(now.hour % 12) or 12}:{now:%M:%S}"
    hpf = doc.data["Contents/content.hpf"].decode("utf-8")
    hpf = re.sub(r"<opf:title\s*/>|<opf:title>.*?</opf:title>", "<opf:title>%s</opf:title>" % title, hpf)
    for key, v in [("creator", ""), ("lastsaveby", ""), ("CreatedDate", utc), ("ModifiedDate", utc), ("date", kdate)]:
        hpf, c = re.subn(r'(<opf:meta name="%s" content="text")(?:\s*/>|>.*?</opf:meta>)' % key,
                         lambda m: m.group(1) + (">%s</opf:meta>" % v if v else "/>"), hpf)
        assert c == 1, ("hpf 메타 항목 없음", key)
    doc.data["Contents/content.hpf"] = hpf.encode("utf-8")
    # 4) zip 항목 시각
    for e in doc.entries: e.date_time = now.timetuple()[:6]
    out = {"prv_text_chars": sum(map(len, lines))}
    out.update(thumb or {})
    return out


def grade(sf):
    return "A" if sf >= 1.0 else ("C" if sf >= 0.9 else ("D" if sf >= 0.75 else "E"))


class B:
    def __init__(self, doc, ps, tmap=None, chap="5"):
        self.doc = doc
        self.chap = chap
        g = lambda i: copy.deepcopy(ps[i])
        self.T = {k: g(i) for k, i in (tmap or TMAP_TEMPLATE1).items()}
        self.anchor = None
        self.sizes = []
        self.num = {"F": 0, "T": 0}; self.lab = {}

    def _add(self, el):
        self.anchor = insert_after(self.anchor, [el]); return el

    KEEP = ("h1", "h2", "h3", "h4", "h5", "tcap")       # 다음 문단과 함께: 제목·표 제목이 쪽 끝에 홀로 남지 않게

    def p(self, key, text):
        el = self._add(new_para(self.T[key], text))
        if key in self.KEEP: keep_with_next(self.doc, el)
        if key == "tcap": self.num["T"] += 1          # 표 제목 = 표 번호
        return el

    def mark(self, kind, key):
        self.lab[kind + ":" + key] = self.num[kind]

    def resolve(self):
        """본문의 §F:키§·§T:키§ → 5.n (그림·표가 추가돼도 참조가 어긋나지 않게)"""
        pat = re.compile(r"§([FT]):(\w+)§(\](?:와|과))?"); n = 0
        def sub(m):
            num = self.lab[m.group(1) + ":" + m.group(2)]
            if not m.group(3): return "%s.%d" % (self.chap, num)
            return "%s.%d]%s" % (self.chap, num, "와" if str(num)[-1] in "2459" else "과")   # 끝자리 읽기: 이·사·오·구 → 와
        for t in self.doc.root.iter(P + "t"):
            if t.text and "§" in t.text:
                t.text = pat.sub(sub, t.text); n += 1
        left = [t.text for t in self.doc.root.iter(P + "t") if t.text and "§" in t.text]
        assert not left, ("참조 미해결", left)
        return n

    def h1(self, t, newpage=False):
        el = self.p("h1", t)
        if newpage: el.set("pageBreak", "1")
        return el
    def h2(self, t): return self.p("h2", t)
    def h3(self, t): return self.p("h3", t)
    def h4(self, t): return self.p("h4", t)
    def h5(self, t): return self.p("h5", t)
    def t11(self, t): return self.p("b11", t)      # 5.x.x 본문
    def tga(self, t): return self.p("bga", t)      # 가. 본문
    def t1(self, t): return self.p("b1", t)        # 1) 본문
    def t5(self, t): return self.p("b5", t)        # ① 본문
    def note(self, t): return self.p("note", t)
    def sp(self): return self.p("sp", "")

    def table(self, caption, data, widths=None, header_rows=1, merges=(), key=None):
        if caption:
            self.p("tcap", caption)
            if key: self.mark("T", key)
        ncols = max(len(r) for r in data)
        data = [r + [""] * (ncols - len(r)) for r in data]
        tp = new_table(self.doc, self.T["tbl"], len(data), ncols, data, widths, header_rows)
        tbl = tp.find(".//" + P + "tbl")
        for (r0, c0, r1, c1) in merges:
            merge_cells(tbl, r0, c0, r1, c1)
        self.tidy(tbl, header_rows)
        self._add(tp); self.sp(); return tbl

    def tidy(self, tbl, header_rows=1):
        """표 선(바깥 0.4 mm, 머리행 아래 이중선 0.5 mm, 안쪽 0.12 mm) + 열 폭·행 높이 정리"""
        set_table_lines(self.doc, tbl, header_rows)
        self.sizes.append(autosize_table(self.doc, tbl, header_rows))

    def clone(self, key, caption=None):
        el = self._add(copy.deepcopy(self.T[key]))
        return el

    def fig(self, path, caption, max_w=44000, key=None):
        fp = self._add(copy.deepcopy(self.T["fig"])); cp = self._add(copy.deepcopy(self.T["figcap"]))
        self.num["F"] += 1
        if key: self.mark("F", key)
        keep_with_next(self.doc, fp)                    # 그림과 아래 캡션을 같은 쪽에
        pic = list(fp.iter(P + "pic"))[0]
        im = Image.open(path); w, h = im.size; ext = path.rsplit(".", 1)[-1].lower()
        ref = self.doc.add_image(open(path, "rb").read(), ext)
        self.doc.swap_pic(pic, ref, w, h, width_hu=max_w, max_width_hu=max_w)
        self.doc.set_para_text(cp, caption)
        for q in (fp, cp):
            for la in q.findall(P + "linesegarray"): q.remove(la)
        self.sp()
        return fp

    def eq(self, script, prefix=None, nchar=None):
        """수식 문단. prefix 있으면 '∘… : [수식]' 형태(①내용 문단), 없으면 가.내용 문단의 단독 수식"""
        el = copy.deepcopy(self.T["eqt" if prefix is not None else "eq"])
        e = list(el.iter(P + "equation"))[0]
        e.find(P + "script").text = script
        vis = nchar or len(re.sub(r"\b(rm|TIMES|over|times|sqrt|upsilon|gamma|phi|lambda|LEQ|GEQ|it)\b|[_{}`~ ]", "", script))
        e.find(P + "sz").set("width", str(min(44000, int(560 * vis + 1200))))
        if prefix is not None:
            ts = el.findall(".//" + P + "t"); ts[0].text = prefix
        for la in el.findall(P + "linesegarray"): el.remove(la)
        return self._add(el)


def replace_text_everywhere(el, old, new):
    for t in el.iter(P + "t"):
        if t.text and old in t.text: t.text = t.text.replace(old, new)


def finish(doc, b, out, title, thumb_fix=None, layout_ratio=0.9):
    """조립 마무리: 참조 치환 → 표 뒤 '주)' 문단을 표와 같은 쪽에 → 긴 표 처리 → 개체 번호·이미지 정리 → 메타데이터 → 저장·검증"""
    print("참조 치환:", b.resolve(), "문단", b.lab)
    tops = doc.paragraphs()
    for p, q in zip(tops, tops[1:]):
        if p.find(".//" + P + "tbl") is not None and para_text(q).strip().startswith("주)"):
            keep_with_next(doc, p)
    print("레이아웃:", fix_layout(doc, ratio=layout_ratio))
    print("표 행 높이:", [s["rows"] for s in b.sizes])
    doc.renumber_objects()
    doc.prune_images()
    commit_header(doc)
    print("패키지 정리:", scrub_package(doc, title, thumb_fix))
    doc.save(out)
    rep = doc.verify(out)
    print("저장:", out, os.path.getsize(out) // 1024, "KB")
    print("검증:", {k: v for k, v in rep.items()})
    return rep
