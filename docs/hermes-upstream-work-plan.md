# Hermes 0-turn 업스트림 작업계획서 (정정)

> 무료/소형 에이전트에게 일을 맡길 때는 이 문서 대신
> **[`docs/HERMES_AGENT_EXECUTOR_PLAN.md`](HERMES_AGENT_EXECUTOR_PLAN.md)** 만 주어라.
> 그 문서는 저장소 혼동 방지와 금지 목록이 더 구체적이다.


작성: 2026-08-21  
정정: 2026-08-21 — 이미 열린 업스트림 PR(#87441)과 **새 PR** 규칙을 반영  
실행 주체: **당신** (`kdkrkwhr`) — 핸드오프. AI 커밋을 hermes-agent에 남기지 마세요.  
목표: `agent-drift-guard`에서 증명을 끝낸 뒤, 당신이 직접 포크에서 검증하고 `NousResearch/hermes-agent`에 **별도의 새 PR**을 연다.

---

## 정정 요약 (이번 판에서 바뀐 것)

기존 계획의 “그다음에 업스트림 PR 버튼을 누르면 됩니다”는 오해의 소지가 있습니다.  
이미 업스트림 PR이 하나 열려 있고, **그걸 닫거나 재사용하지 않습니다.**

| 항목 | 내용 |
|---|---|
| 이미 열린 PR | [NousResearch/hermes-agent#87441](https://github.com/NousResearch/hermes-agent/pull/87441) `feat(watch): add native watch tool` |
| 헤드 브랜치 | `kdkrkwhr:feat/native-watch-tool` |
| 이 작업과의 관계 | **무관.** watch 툴. 0-turn/drift-guard와 커밋·파일을 섞지 말 것 |
| 이번 작업 | **새 브랜치 + 새 PR.** #87441은 open 유지 |

GitHub은 같은 포크에서 브랜치만 다르면 PR을 여러 개 열 수 있습니다. 그렇게 하면 됩니다.

하지 말 것:

- `feat/native-watch-tool`에 0-turn 커밋을 추가로 푸시 (#87441 범위가 오염됨)
- #87441을 닫고 한 PR로 합치기
- #87441 위에 rebase해서 그 PR에 커밋 얹기
- 새 PR의 base를 watch 브랜치로 두기 (watch diff가 같이 올라감)

할 것:

- base는 **upstream `main`** (`NousResearch/hermes-agent`의 최신 `main`)
- 브랜치 이름 예: `feat/session-busy-hook` (generic hook PR일 때) 또는 `feat/verify-drift-guard-plugin` (포크 로컬 검증만)
- `git checkout -b …` 의 출발점은 `feat/native-watch-tool`이 아니라 `upstream/main`

---

## 한 줄 전략

**코어에 `agent-drift-guard`를 넣지 마세요.**  
NousResearch CONTRIBUTING은 서드파티 연동을 in-tree `plugins/`에 넣는 PR을 닫습니다.  
대신:

1. 플러그인은 **standalone** (`~/.hermes/plugins/` 또는 `agent-drift-guard` 안의 플러그인 디렉터리).
2. 훅만으로 부족하면, 업스트림 **새 PR**은 **일반 훅 표면을 넓히는 것**만. drift-guard 이름을 코어에 넣지 않음.
3. `kdkrkwhr/hermes-agent` 포크는 **로컬 검증 + (필요 시) generic hook용 새 브랜치** 용.
4. #87441은 그대로 두고, 0-turn은 다른 PR 번호로 간다.

---

## 이미 끝난 증명 (`agent-drift-guard`)

브랜치: `cursor/public-api-injection-3e26`  
관련: `src/drift_guard/adapters/hermes.py`, `tests/test_hermes_loop.py`, `docs/hermes-wiring.md`

| 증명 | 결과 |
|---|---|
| 라디오는 모델을 안 부름 | `HermesTurn.wait_for_mention` → `model_calls` 불변 |
| 툴 도중에 transcript에 안 보임 | `complete_tool` 전까지 `transcript == []` |
| 툴 결과에 FIFO appendix | `tool_result_appendix` 헤더 + `- from sender: text` |
| 빈 drain은 no-op | 결과 문자열 그대로 |
| 스레드 라디오 손실 없음 | 50개 메시지 전부 툴 결과에 존재 |
| pytest | 29 passed (`python3 -m pytest -v`) |

이것은 **라이브러리 계약** 증명입니다. 실제 Hermes 프로세스 증명은 아직입니다.

아직 안 된 것:

- `pre_gateway_dispatch`가 busy 세션에서 `skip` 하는지
- `transform_tool_result`가 같은 guard 인스턴스에서 drain 하는지
- 사용자 `/steer`·`/stop`·본인 멘션을 가로채지 않는지
- 실제 `run_conversation()` 호출 횟수가 라디오 때문에 늘지 않는지

---

## 아키텍처 (당신이 만들 것)

```
[다른 에이전트 라디오]
        │
        ▼
pre_gateway_dispatch
  ├─ 세션 busy + 크로스에이전트 라디오 → guard.on_radio_message(); return {action: skip}
  └─ 그 외 (유저, idle, /steer, /stop) → allow (기존 Hermes 동작)
        │
        ▼  (툴 실행 중… 모델 호출 없음)
transform_tool_result
  └─ return append_to_tool_result(result, guard.drain_for_injection())
        │
        ▼
기존 턴 계속 (Hermes가 원래 하려던 다음 LLM 호출)  ← 이것이 0-turn
```

가깝지만 다른 것: `busy_input_mode: steer`는 **유저** 후속 메시지용.  
이 플러그인은 **다른 에이전트 라디오**만. 유저 busy 입력은 건드리지 말 것.

### 세션당 guard

`HermesDriftGuard`는 **세션(또는 running agent)당 하나**.  
전역 싱글톤이면 세션 A 라디오가 세션 B 툴 결과에 붙습니다.

키: `session_key` (`gateway/session.py`의 `build_session_key`와 동일 규칙).  
맵 + lock (`post_tool_call` / `transform_tool_result`는 병렬 툴에서 동시에 올 수 있음).

### 라디오 vs 유저 (반드시 당신이 정할 것)

`skip`을 idle 멘션에 쓰면 봇이 영영 안 답합니다. 규칙 초안:

| 조건 | 동작 |
|---|---|
| `gateway._running_agents`에 이 세션 없음 | `allow` |
| 메시지 타입이 slash (`/steer`, `/stop`, `/new`, …) | `allow` |
| 세션 오너/유저가 직접 말한 busy 입력 | `allow` (steer/queue/interrupt에 맡김) |
| busy + 다른 에이전트/봇 발신 (또는 합의한 prefix, 예: `[radio]`) | `skip` + buffer |

발신자 판별이 플랫폼마다 다릅니다. Telegram bot vs human, Discord bot flag, 자체 AgentRadio 헤더.  
**첫 구현은 판별을 좁게:** 예) `event.text`가 `[radio]`로 시작하거나 `event.source`에 bot flag가 있을 때만 skip.  
넓히기는 그다음.

---

## 왜 in-tree `plugins/agent-drift-guard`를 업스트림하면 안 되나

`NousResearch/hermes-agent` CONTRIBUTING:

- 서드파티 제품 연동은 **standalone plugin repo** (`~/.hermes/plugins/` 또는 pip entry point).
- in-tree `plugins/` 추가는 닫힘.
- 훅이 부족하면 **generic surface를 넓히는 PR** (새 훅/`ctx` 메서드). 코어에 플러그인 이름을 특수 케이스하지 말 것.

따라서:

| 위치 | 역할 |
|---|---|
| `kdkrkwhr/agent-drift-guard` | 라이브러리 + **standalone Hermes 플러그인** + 계약 테스트 |
| `kdkrkwhr/hermes-agent` | 포크에서 플러그인 로드 검증. 코어 수정은 generic hook이 필요할 때만, **새 브랜치** |
| `NousResearch/hermes-agent` **새 PR** | (A) 훅 표면 확장 또는 (B) 코어 패치가 꼭 필요할 때만. drift-guard 디렉터리 없음. **#87441과 별개** |

포크 `plugins/`에 골격을 넣어도 **로컬 실험용**이지, 그 diff를 업스트림 PR에 넣지 마세요.

---

## 파일 맵 (당신이 생성)

### A. `agent-drift-guard` (추천 본진)

```
hermes_plugin/agent-drift-guard/
  plugin.yaml
  __init__.py          # register(ctx)
  radio.py             # pre_gateway_dispatch
  inject_hook.py       # transform_tool_result
  session_guards.py    # session_key → HermesDriftGuard (lock)
tests/test_hermes_plugin.py
docs/hermes-plugin.md
```

`plugin.yaml` 초안:

```yaml
name: agent-drift-guard
version: "0.0.1"
description: 0-turn buffer for cross-agent radio; inject at tool-result boundary
hooks:
  - pre_gateway_dispatch
  - transform_tool_result
```

`__init__.py` 초안:

```python
def register(ctx):
    from .radio import on_pre_gateway_dispatch
    from .inject_hook import on_transform_tool_result

    ctx.register_hook("pre_gateway_dispatch", on_pre_gateway_dispatch)
    ctx.register_hook("transform_tool_result", on_transform_tool_result)
```

`on_pre_gateway_dispatch` 초안:

```python
def on_pre_gateway_dispatch(event, gateway, session_store, **kwargs):
    if not _is_cross_agent_radio(event):
        return None  # allow
    session_key = _session_key(event)
    running = getattr(gateway, "_running_agents", {}).get(session_key)
    if running is None:
        return None  # idle: 정상 턴
    guard = _guard_for(session_key)
    guard.on_radio_message({
        "text": getattr(event, "text", "") or "",
        "sender": _sender(event),
        "ts": getattr(event, "timestamp", None),
    })
    return {"action": "skip", "reason": "drift-guard-radio-buffered"}
```

`on_transform_tool_result` 초안:

```python
def on_transform_tool_result(tool_name, args, result, task_id="", session_id="", **kwargs):
    from drift_guard.adapters.hermes import append_to_tool_result
    guard = _guard_for(session_id)  # session_id가 키와 다르면 매핑 테이블 필요
    block = guard.drain_for_injection()
    if not block:
        return None
    if not isinstance(result, str):
        return None
    return append_to_tool_result(result, block)
```

주의: `transform_tool_result`의 `session_id`와 gateway `session_key`가 다를 수 있음.  
첫 테스트에서 둘을 로그로 찍고, 키가 다르면 `session_guards.py`에 별칭 맵을 둠.

설치 (로컬 Hermes):

```bash
# agent-drift-guard를 editable로
pip install -e /path/to/agent-drift-guard

# 플러그인 디렉터리 링크
ln -s /path/to/agent-drift-guard/hermes_plugin/agent-drift-guard \
      ~/.hermes/plugins/agent-drift-guard
```

### B. `kdkrkwhr/hermes-agent` 포크 (검증 + 새 PR 브랜치)

clone 후 **watch 브랜치에 있지 않은지** 확인하세요.

```bash
git clone git@github.com:kdkrkwhr/hermes-agent.git
cd hermes-agent
git remote add upstream git@github.com:NousResearch/hermes-agent.git   # 이미 있으면 skip
git fetch upstream
git checkout -b feat/session-busy-hook upstream/main   # 당신 브랜치, 당신 커밋만
# 확인: git branch --show-current  → feat/native-watch-tool 이면 안 됨
```

업스트림에 올릴 코어가 없다면 포크에는 검증 메모만:

```
docs/local/drift-guard-verify.md   # 재현 절차, 당신 작성. 업스트림 PR에 넣지 말 것
```

플러그인 코드를 포크 `plugins/`에 복사하지 말 것. `~/.hermes/plugins/` 심볼릭 링크만.

generic hook이 부족할 때만 이 새 브랜치에서 코어를 만짐. 후보:

1. `pre_gateway_dispatch`는 이미 skip/rewrite/allow — **라디오 버퍼에는 충분할 가능성 큼**. 먼저 플러그인만.
2. `transform_tool_result`는 이미 툴 결과 치환 — **appendix에는 충분할 가능성 큼**.
3. 부족할 수 있는 점:
   - busy 판별이 public이 아님 (`_running_agents`는 private). 업스트림 새 PR이라면 `gateway.session_is_busy(session_key)` 같은 **generic** API.
   - idle일 때 라디오를 skip하면 안 됨. 훅 payload에 `agent_busy: bool`이 있으면 private 접근이 사라짐.
   - `transform_tool_result`에 안정적인 `session_key`가 없으면 그 필드를 generic하게 추가.

**코어 PR 문구 원칙:** “agent-drift-guard를 넣는다”가 아니라 “플러그인이 busy inbound를 버퍼하고 툴 결과에 붙일 수 있게 훅을 연다”.  
Related에 #87441을 걸지 말 것 (다른 작업).

---

## 검증 매트릭스 (충분하다고 말할 증거)

라이브러리 pytest만으로는 업스트림 리뷰어에게 부족합니다. 아래를 당신이 돌린 로그/스크린과 함께 붙이세요.

### 1. agent-drift-guard (이미 있음, 재실행)

```bash
cd agent-drift-guard
python3 -m pytest -v
python3 examples/hermes_loop.py
```

기대: 29 passed, `model_calls`가 라디오 전후 1.

### 2. 플러그인 단위 테스트 (당신이 추가)

`tests/test_hermes_plugin.py` — Hermes를 설치하지 않고 mock.

케이스:

1. idle + radio 모양 메시지 → `None` (allow), pending 0  
2. busy + radio → `{action: skip}`, pending 1, mock `run_conversation` 호출 0  
3. busy + `/stop` → `None`  
4. busy + 오너 유저 텍스트 → `None`  
5. transform, pending 있음 → result 끝에 appendix, pending 0  
6. transform, pending 없음 → `None` (원본 유지)  
7. 두 세션 busy → A 라디오가 B 툴 결과에 안 붙음  

TDD: 실패하는 테스트 먼저.

### 3. 포크에서 실 Hermes (최소 수동)

환경: 로컬 `kdkrkwhr/hermes-agent`의 **`upstream/main` 기반 브랜치** (watch 브랜치 아님), 싼 모델, 게이트웨이 또는 CLI.

시나리오 스크립트 (`docs/local/drift-guard-verify.md`에 당신이 기록):

1. 에이전트가 긴 `terminal sleep 8` (또는 동등) 툴을 실행하게 함.  
2. 툴 도중에 `[radio] ping from agent-2` 를 같은 세션으로 넣음.  
3. **실패 조건:** 즉시 새 어시스턴트 턴/interrupt ack가 라디오 때문에 생김.  
4. **성공 조건:** 툴 결과가 끝난 뒤에야 모델이 이어 말하고, 그 컨텍스트에  
   `[drift-guard site=tool_result_appendix]` / `from agent-2` 가 보임.  
5. 카운터: 라디오 직후 `run_conversation` 또는 API call 로그가 **증가하지 않음**.  
   증가하는 호출은 “툴 이후 원래 이어가던 호출” 하나뿐.

가능하면 로그에서 `model_calls` / `api_call_count` before/after를 숫자로 남김.

### 4. 회귀 (건드리면 안 되는 것)

- `/steer` 가 여전히 `running_agent.steer(...)` 로 감  
- `/stop` interrupt  
- idle @mention 은 정상 응답  
- `require_mention` 그룹챗 기존 동작  
- **#87441 watch 툴 동작/테스트** — 이 작업 브랜치에 watch 파일이 있으면 잘못된 출발점

---

## 당신이 실행할 순서 (커밋은 전부 당신 계정)

### Phase 0 — 중복 검색 + 열린 PR 확인

```bash
gh pr view 87441 --repo NousResearch/hermes-agent
# 기대: OPEN, head = kdkrkwhr:feat/native-watch-tool  → 건드리지 않음

gh search issues --repo NousResearch/hermes-agent "0-turn OR drift-guard OR busy radio OR steer tool result"
gh search prs --repo NousResearch/hermes-agent --state all "pre_gateway_dispatch transform_tool_result"
```

steer / observe-but-don’t-invoke (#15621 계열)와 겹치면, 새 기능이 아니라 그 이슈에 플러그인으로 해결한다고 코멘트.  
#87441에는 코멘트하지 말 것 (범위가 다름).

### Phase 1 — 플러그인 + mock 테스트 (`agent-drift-guard`)

1. 위 파일 맵대로 `hermes_plugin/` 추가.  
2. `tests/test_hermes_plugin.py` TDD.  
3. `docs/hermes-plugin.md`에 설치 한 줄 (`ln -s ... ~/.hermes/plugins/`).  
4. 커밋 메시지 예: `feat: add standalone Hermes plugin for 0-turn radio`.

이 레포 커밋은 당신의 로컬/계정에서. 기존 Cloud Agent 커밋이 있는 브랜치를 그대로 쓰지 말고, 필요하면 squash 후 당신 이름으로 새 브랜치.

### Phase 2 — 포크에서 로드 확인 (`kdkrkwhr/hermes-agent`)

위의 checkout 명령을 그대로: **`upstream/main`에서 새 브랜치**.  
`feat/native-watch-tool`이 current이면 즉시 빠져나오세요.

```bash
git branch --show-current
# feat/native-watch-tool  → git checkout -b feat/session-busy-hook upstream/main
```

### Phase 3 — 훅 부족 여부 판정

플러그인이 동작하면 **코어 새 PR 없이** Discord `#plugins-skills-and-skins`에 standalone 플러그인으로 공개하는 길이 CONTRIBUTING 정석.

부족한 경우에만 Phase 4.

부족 판정 체크리스트:

- [ ] `_running_agents` 없이 busy를 알 수 없다  
- [ ] `transform_tool_result`에 세션 키가 없어 drain이 엉뚱한 guard로 간다  
- [ ] skip이 pairing/auth까지 깨서 라디오가 아닌 유저 DM을 삼킨다  

하나라도 체크되면 generic hook **새 PR**.

### Phase 4 — (조건부) NousResearch **새 PR**

#87441을 업데이트하지 않습니다. 헤드를 `feat/session-busy-hook`로 해서 **create**.

```bash
git push -u origin feat/session-busy-hook
gh pr create --repo NousResearch/hermes-agent \
  --base main \
  --head kdkrkwhr:feat/session-busy-hook \
  --title "feat(gateway): let plugins see whether a session is busy"
# --base 가 feat/native-watch-tool 이면 잘못됨
```

**PR 종류 A — 훅 표면만 (권장, 작음)**

예: `GatewayRunner.session_is_busy(session_key) -> bool`  
예: `transform_tool_result` kwargs에 `session_key`  
테스트는 Hermes 기존 `tests/` 스타일. drift-guard import 금지.

제목 예: `feat(plugins): expose session busy flag to pre_gateway_dispatch`

본문에 0-turn 동기를 쓰되, 구현은 generic.  
“we need this for agent-drift-guard”는 Related에만.  
Related에 #87441을 넣지 말 것.

PR 본문 맨 위에 한 줄:

> Separate from #87441 (native watch tool). Different branch, no overlapping files.

**PR 종류 B — tool_executor / gateway 코어에 appendix (비권장)**

`docs/hermes-wiring.md`의 직접 패치. 리뷰 크고, 플러그인으로 되면 거절 사유.  
종류 B도 **새 PR**. #87441에 얹지 않음.

종류 B는 A가 막혔을 때만.

### Phase 5 — 새 PR 체크리스트 (CONTRIBUTING)

- `gh pr view`로 헤드 브랜치가 `feat/native-watch-tool`이 **아님**을 확인  
- Files changed에 watch 툴 파일이 **없음**을 확인  
- 중복 검색 결과 링크  
- 관심사: bug/robustness (reasoning drift)로 프레이밍. “새 제품 연동”으로 쓰지 말 것  
- 테스트 + 재현 절차  
- 코어에 `import drift_guard` 없음  
- 새 in-tree `plugins/agent-drift-guard/` 없음  
- 보안: 라디오 내용이 다른 세션/유저에게 새지 않음  
- 기존 steer/interrupt 테스트 통과  

---

## 카피용: 업스트림 **새 PR** 초안 (generic hook일 때)

Title: `feat(gateway): let plugins see whether a session is busy`

Body:

```markdown
## Note

Separate from #87441 (native watch tool). This PR uses branch
`feat/session-busy-hook` off upstream `main`. No overlapping files.

## Why

Plugins that implement observe-but-don't-invoke (buffer inbound while a
turn is in a tool call, inject at the next tool result) cannot currently
detect "agent is mid-turn" without reading GatewayRunner._running_agents.

## What

- Add `GatewayRunner.session_is_busy(session_key) -> bool` (public).
- Pass `agent_busy: bool` into `pre_gateway_dispatch` context.

No behavior change when no plugin is loaded. No third-party plugin is
vendored.

## Tests

- idle → False
- running agent in _running_agents → True
- pre_gateway_dispatch callback receives agent_busy

## Out of scope

Installing or depending on agent-drift-guard.
Native watch tool (#87441).
```

---

## 하지 말 것

- Cloud Agent / 다른 봇 Git 유저로 hermes-agent에 커밋  
- `feat/native-watch-tool` 또는 #87441에 이 작업 커밋을 푸시  
- 새 PR의 base/head를 watch 브랜치로 설정  
- NousResearch PR에 `plugins/agent-drift-guard/` 디렉터리  
- 모든 busy 메시지를 skip (유저 `/steer` 사망)  
- idle 멘션 skip (봇 침묵)  
- `pending_user` injection site (Hermes에서 새 턴으로 보임)  
- 메시지 coalesce/staleness (라이브러리 시뮬레이션이 아직 불필요라고 함)  
- drift-guard를 Hermes 런타임 의존성으로 강제 (플러그인은 extras/optional)

---

## 완료 정의

당신이 “충분하다”고 말할 수 있는 상태:

1. `agent-drift-guard` pytest + 플러그인 mock 테스트 전부 초록.  
2. 포크에서 수동 시나리오 1회: 툴 도중 라디오 → 새 턴 없음 → 툴 결과에 appendix. (`upstream/main` 기반 브랜치)  
3. 업스트림은 (플러그인 README만) 또는 (**#87441과 다른** 작은 generic hook PR) 중 하나. 코어에 라이브러리 없음.  
4. #87441은 여전히 본인 watch 작업만 담고 있음.
)
