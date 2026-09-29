# 9/18 초기 원형 (보관용)

- `tunnel_geom.py` 3심원 격자(천단 0°·시계방향 각 규약) — 실제 작업은 `../lining/geom.py`(설계 원호 DXF 판독, 반시계 규약)로 했다.
- `verify_weight.py` 자중 검증(NX 반력 합 vs 기하) — 엔진에서는 `lining.post.report` 의 ΣRz 출력으로 대신한다.
- `sources.py` 값마다 출처 강제 — 엔진에서는 `lining.json` 의 `src`, `(확인 필요)` 자리표시, `Project.require()` 로 대신한다.

새 작업에 쓰지 않는다.
