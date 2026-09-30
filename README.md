# Midas-tunnel — 터널 콘크리트 라이닝 안전성평가 자동화

설계서·도면에서 해석조건을 읽어 **이 PC의 MIDAS CIVIL NX를 Open API로 직접 조작**해 빔-스프링(보 요소 + 압축전용 지반스프링) 모델을 만들고 해석한 뒤, 라이닝 단면을 검토하고(무근·철근, 세부지침 안전율·등급) 삽도와 보고서 5장(hwpx)을 만든다.

공통 도구·설계기준·Claude 운용 규칙은 서브모듈 **`core/`**(= [Midas-core](https://github.com/sjidok750-creator/Midas-core)). 교량은 [Midas-nx](https://github.com/sjidok750-creator/Midas-nx).
Claude 절차서는 스킬 **`tunnel-lining`**(`core/claude/skills/tunnel-lining/SKILL.md`).

```bash
git clone --recurse-submodules https://github.com/sjidok750-creator/Midas-tunnel.git
```

## 사용법

```bash
cd tools
python -m lining new <터널명>            # projects/<터널명>/lining.json 틀 — (확인 필요)를 채운다
python -m lining status <터널명>         # 남은 (확인 필요), 해석 태그, 패턴별 Ks·PV·Pw
python -m lining geom <터널명>           # 단면 형상 점검(설계 B·Ht·A·R 과 대조)
python -m lining selftest <터널명>       # 검토식 역검산(설계 구조계산서 값)
python -m lining run <터널명> [태그…]     # MIDAS 해석 — NX 에서 Apps > API Settings > Connect 가 켜져 있어야 한다
python -m lining capture <터널명>        # 하중조합별 NX 부재력도 캡처
python -m lining data <터널명>           # runs/report_data.json (지배값·안전율·반력·포락)
python -m lining figs <터널명>           # 모델도·하중재하도·해석결과도·P-M·안전율
python -m lining location <터널명>       # 검토 위치도(실제 평면·종단면도 도곽 위에 표기)
python -m lining umd <터널명> <태그> [부재…]  # midas UMD(RC/Wall) 계수하중 붙여넣기 표·단면 설정값 → P-M 그림은 core/tools/umd_pm.py
```
보고서 본문은 터널마다 스크립트를 쓴다 — `tools/report_ch5.py`(양식 hwpx 복제·표·그림·수식·자동번호·메타데이터) 위에 본문만.

## 구조

| 폴더 | 내용 |
|---|---|
| `core/` | 서브모듈. `core/tools`(NX API·MCT·DXF·HWPX·HWP 판독), `core/references`(설계기준) |
| `tools/lining/` | 엔진: `project`(입력·파생값·(확인 필요) 점검), `geom`(3심원 원호 → 격자), `model`(MCT·COMP 링크·단부 스프링·온도·해석·결과표), `post`, `check`(KCI 2012 무근·RC P-M·균열, 세부지침 등급), `data`, `figs`, `capture`, `location`, `umd`(UMD 입력 표), `lining_template.json` |
| `tools/report_ch5.py` | 보고서 장 조립 도우미 |
| `projects/<터널>/` | **로컬 전용**(설계서 추출본·결과·보고서 본문 — 저장소에 올리지 않음) |

## 해석 규약 (실증 프로젝트에서 검증)

- 절점 법선방향 압축전용 링크 k = Ks × 분담길이, Ks = Es/((1+ν)R), R = √(A/π). 하중조합마다 계수하중을 한 하중케이스로(압축전용 → 중첩 불가).
- 하중 형상 기본 `ncos`(법선, P·cosθ, 스프링라인 아래 0) — 도로설계편람 607 예제 재현이 가장 가깝다. 민감도: `vertical`(중력방향), 토피보정 αH.
- 측벽 하단 기본 **단부 스프링**(라이닝 축선 방향 압축전용, K = kV·B, kV = α·E0/0.3·(√B/0.3)^-3/4) — 도로공사 설계실무자료집(2017) 7-3. 설계 조건 비교는 `pin`.
- 엔진 이관 회귀 점검(2026-09-29, 실증 프로젝트): MCT 24/24 바이트 동일, 링크 강성 차 0, 집계 차 0, 삽도 28장 픽셀 동일, 5장 본문 동일, MIDAS 재해석(P-5 단부 스프링) 결과 차 0.

## 제한

- 단면은 3심원(천단 동심 2 + 좌·우 측벽 원호) 인버트 없는 형상만. 인버트·5심원은 두 번째 터널에서 확장.
- 위치도 상수(측점↔도면 좌표, 도곽, 뷰포트)는 도면마다 손으로 찾아 넣는다(`location.py` 머리말에 찾는 법).
- 보고서 5장 본문은 범용 생성기가 없다 — 실증 프로젝트 스크립트를 복사해 고친다.

## 원칙

- 값마다 출처(`src`)를 적고, 모르는 값은 `(확인 필요)`로 둔다 — 남아 있으면 해석 명령이 멈춘다.
- 설계서 수식·표 병합 셀은 텍스트 추출에서 빠진다(`core/tools/hwp5_eqn.py`, 표 셀 판독). 무근/철근은 라이닝 구조도 시트 제목과 지질·지보패턴 개요도 「라이닝 철근보강」 행까지 확인한다.
- 지진은 내진성능평가에서 따로 하므로 제외. MCT 문법은 NX 내보내기와 대조한다.
- 발주처 도면·설계서·NX 바이너리·납품 문서·터널별 작업 폴더는 올리지 않는다(공개 저장소).
