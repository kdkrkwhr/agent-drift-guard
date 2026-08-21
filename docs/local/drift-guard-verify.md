# T4 검증 보고서 - 플러그인 로드 + 수동 0-turn 시나리오

작성: ops (kanban t_77a52340) / 2026-08-21
대상 저장소: D:\develop\project\agent-drift-guard
검증 범위: (1) Hermes `~/.hermes/plugins` 심볼릭 링크 로드 경로, (2) 툴 도중 [radio] 주입 시나리오 (새 턴 없음 + 툴결과 appendix)

## 1. 플러그인 로드 경로 검증

### 와이어링
- 대상 플러그인 디렉터리: `D:\develop\project\agent-drift-guard\hermes_plugin\agent-drift-guard` (T2가 실제 파일 생성 예정)
- 심볼릭 링크 생성:
  `D:\develop\e2e\hermes\profiles\ops\plugins\agent-drift-guard` -> 위 디렉터리
- 방법: MSYS `ln -s` (타깃 디렉터리는 T2 생성 전이라 먼저 생성 후 링크). 링크 해석 정상 확인됨.

### 발견(discovery) 증명
- Hermes 플러그인 로더는 `get_hermes_home()/plugins/<name>/plugin.yaml` 을 스캔 (hermes_cli/config.py:5782).
  `HERMES_HOME` = `D:\develop\e2e\hermes\profiles\ops` 이므로 스캔 루트는 `.../profiles/ops/plugins`.
- 검증: 임시 probe 플러그인 `_driftguard_probe` (실제 플러그인 파일과 무관)를 `plugins/` 에 두고
  `hermes plugins list` 실행 -> `Source: user` 로 목록에 노출됨을 확인.
- 결론: 심볼릭 링크로 걸어둔 디렉터리도 Hermes가 `user` 플러그인으로 정상 발견한다. probe는 검증 직후 삭제.
- 주의: 플러그인은 opt-in. 목록에 뜨는 것과 로드(enable)는 별개. 실제 활성화는 `hermes plugins enable agent-drift-guard` (T2 완료 후).

## 2. 0-turn 시나리오 검증 (수동, 실제 코드 경로)

### 시나리오
1. [radio] 메시지가 툴 호출 도중 도착 (백그라운드 워처가 `on_radio_message` 호출).
2. 어댑터가 버퍼에만 적재. 모델 호출 안 함 (0-turn).
3. 툴 완료 시 런타임이 버퍼 드레인 -> 툴 결과에 appendix로 첨부.
4. 단언: 새 LLM 턴 0회, appendix 존재, 버퍼 비움.

### 하네스
- 신규: `examples/verify_drift_guard_0turn.py`
- 실제 코드 사용: `src/drift_guard/adapters/hermes.py` 의 `HermesDriftGuard.on_radio_message` / `on_tool_call_complete`.
- 모델은 `FakeModel` 스텁으로 대체 (카드 범위는 0-turn 계약 검증, 라이브 LLM 호출 아님).

### 실행 결과
```
$ PYTHONPATH=src python3 examples/verify_drift_guard_0turn.py
[verify] 0-turn scenario PASS
  - model extra turns invoked : 0 (expect 0)
  - tool result appendix      : ['[radio] pm: status check - are you done?']
  - buffer after drain        : 0 pending (expect 0)
  - conclusion                : radio msg held during tool call, appended at step boundary, no new LLM turn
```

## 3. 보조 검증 (기존 하네스)

| 항목 | 명령 | 결과 |
|------|------|------|
| 단위 테스트 | `python3 -m pytest tests/ -q` (pyproject pythonpath) | 3 passed |
| e2e 시뮬레이션 | `PYTHONPATH=src python3 examples/simulation.py` | asyncio 200/200, 0 lost/dup/mid-step; threaded 32000/32000, 0 lost |

## 4. 한계 / 다음 조치

- T2가 `hermes_plugin/agent-drift-guard/{plugin.yaml,__init__.py,radio.py,inject_hook.py,session_guards.py}` 를 생성하면
  본 심볼릭 링크가 바로 그 파일들을 가리킨다 (링크는 디렉터리 단위). 추가 와이어링 불필요.
- 실제 Hermes agent-loop에 어댑터를 꽂는 시밍(툴 익스큐터 후킹)은 T2/T5 범위. 본 카드는 0-turn 계약과 로드 경로만 증명.
- 활성화 테스트 (`hermes plugins enable` 후 게이트웨이 로드)는 T2 완료 + 대장님 승인 후 수행 권장.
