# Midas-tunnel — 터널 라이닝 정밀안전진단 해석 자동화

터널 준공도면(라이닝 표준단면·지보패턴)과 진단 조사값(GPR 두께·배면공동, 코어 강도, 균열)을 주면 Claude가 **이 PC의 CIVIL NX를 Open API로 직접 조작**해 빔-스프링(보 요소 + 압축전용 지반스프링) 모델을 만들고 해석하여 라이닝 단면을 검토하고 보고서 5장(hwpx)을 조립한다.

공통 도구·설계기준·Claude 운용 규칙은 서브모듈 **`core/`**(= [Midas-core](https://github.com/sjidok750-creator/Midas-core)). 교량은 [Midas-nx](https://github.com/sjidok750-creator/Midas-nx).

```bash
git clone --recurse-submodules https://github.com/sjidok750-creator/Midas-tunnel.git
```

## 계획

[터널_라이닝_해석툴_계획_2026-09-18.md](터널_라이닝_해석툴_계획_2026-09-18.md) — 모델 방식(빔-스프링, CIVIL NX), 재사용/신규 부품, 단계·기간, 대표님 결정 필요 항목.

## 예정 구조

| 폴더 | 내용 |
|---|---|
| `core/` | 서브모듈. `core/tools`(NX API·MCT·DXF·HWPX), `core/references`(설계기준 — 터널 기준 KDS 27·편람 제6편·세부지침 터널편은 확보 후 추가) |
| `tools/` | 터널 전용 도구: `tunnel_geom.py`(표준단면·패턴표 판독기) |
| `projects/<터널>/` | `lining_model.py`(빔-스프링 MCT·NX 해석·자중 검증), `lining_check.py`(무근 허용응력 / 철근 P-M), 제원서·조사 제원서 JSON, `runs/`(결과) |

## 원칙

- 진단 툴이다. 입력은 설계값이 아니라 조사값이며, "설계 상태"와 "조사 상태" 두 모델을 나란히 계산한다.
- 스프링 상수·이완하중·허용응력은 `core/references`의 원문에서 조항을 확인한 뒤에만 쓴다. 원문이 없으면 계산기를 시작하지 않는다.
- 지진은 내진성능평가에서 따로 하므로 제외. MCT 문법은 NX 내보내기와 대조한다.
- 발주처 도면·NX 바이너리·납품 문서는 올리지 않는다.
