# T1 사실 보고서 - agent-drift-guard 테스트 환경 수정 + 현상 재확인

작성: ops (kanban t_59fcb8d4) / 2026-08-21

## 1. pytest CollectionError 원인 (근거 포함)

증상:
```
ERROR collecting tests/test_buffer.py
tests/test_buffer.py:1: from drift_guard.buffer import DriftGuardBuffer
E   ModuleNotFoundError: No module named 'drift_guard'
```

근본 원인: `src/drift_guard/` 패키지에 `__init__.py`가 없다.
그래서 `setup.py`의 `find_packages(where="src")`가 패키지를 0개로 인식하고,
커밋된 `src/agent_drift_guard.egg-info/top_level.txt`가 **빈 파일**이다.
결과적으로 `pip install -e .` 로 만들어진 editable 링크가 `drift_guard` 모듈을
가리키지 않아, pytest가 임포트하지 못하고 CollectionError 발생.

확인 명령/결과:
- `python3 -c "import drift_guard"` -> ModuleNotFoundError (설치 없이)
- egg-info `top_level.txt` 내용 = 빈 줄 (패키지 0개 인식 증거)

## 2. 적용한 수정

파일: `pyproject.toml` (소스 코드/패키지 구조 변경 없음)

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

이유: pytest 7+ 가 pyproject.toml 의 `pythonpath` 를 수집 시 sys.path[0] 에 주입.
`__init__.py` 추가나 `pip install -e` 재설치 없이, **아무 환경변수/설치 없이** pytest 가
모듈을 찾는다. 저장소에 커밋되므로 클론 후 바로 동작.

## 3. 검증 결과

수정 후, **설치 없이 / PYTHONPATH 없이** 실행:

```
$ env -u PYTHONPATH python3 -m pytest -q
...                                                                      [100%]
3 passed in 0.04s
```

- test_buffer 실행 초록(3 passed) 확인됨.
- 추가 보강: `python3 -m pip uninstall -y agent-drift-guard` 로 editable 제거 후에도
  pytest 는 여전히 3 passed (오직 pyproject fix 만으로 동작 확인).
- 예시 `examples/simulation.py` (asyncio 0-turn invariant + threaded race probe)
  `PYTHONPATH=src python3 examples/simulation.py` 로 실행 시 정상:
  200 sent/200 delivered, 0 lost/0 dup/0 mid-step, threaded 32000 전송 0 lost.

## 4. 카드 본문 대안(PYTHONPATH / pip install -e) 실제 동작 재확인

- `PYTHONPATH=src python3 -m pytest tests/` -> 3 passed. (직접 실행 시 해결되나,
  env 세팅이 스크립트/CI 에서 빠지면 다시 깨짐. 영속성 없음.)
- `pip install -e .` -> 이번 신규 설치에서는 `import drift_guard` 성공(OK imported).
  단, 커밋된 egg-info 가 stale(빈 top_level) 상태여서 재설치 전엔 깨져 보였음.
  editable 이므로 src 변경 시 재설치 불필요. but 커밋된 egg-info 자체가 오염됨.

결론: 두 대안 모두 "이번에는" 동작하나, **pyproject `pythonpath` 방식이 가장 견고**
(설치/환경변수 0개, 커밋 즉시 적용). 단, 이 방식은 pytest 수집 경로만 고침.
`import drift_guard` 가 임의 컨텍스트(예: 다른 프로젝트에서 import)에서도 전역적으로
되길 원하면 `pip install -e .` (지금은 동작) 또는 `__init__.py` 추가 + find_packages 유지가 필요.

## 5. 문서 claims("29 passed", "hermes_loop") 재확인 -> 존재하지 않음 (팩트)

전수 탐색 대상: repo 전체 (README.md, 모든 *.md/*.py/*.txt/*.rst, egg-info 포함).
검색 패턴: `29 passed`, `hermes_loop`, `hermes-loop`, `passed`.

결과: **매칭 0건**. README.md 는 테스트 카운트 클레임 자체가 없음.
"Status: Early research" 수준의 개념 설명만 존재.
tests/ 도 test_buffer.py 단 3개 테스트뿐이라 "29 passed" 는 이 repo 에서 불가능한 수치.

=> 카드 본문의 "문서 claims(29 passed, hermes_loop)가 main에 없는 것" 은
**사실로 확인됨**: 해당 claims 자체가 main(및 전체 repo) 어디에도 존재하지 않음.
(메모리상 hermes-agent OSS PR #87441 본문이 "19 passed" 였던 맥락과 혼동된 것으로 추정.
이 repo 의 문서/코드에는 해당 문자열이 없으므로 수정할 문서 클레임도 없음.)

## 6. 권고

1. 커밋 대상: `pyproject.toml` 수정만 스테이징 권장 (egg-info/__pycache__ 는 제외).
2. stale egg-info(`src/agent_drift_guard.egg-info/`)는 untracked 노이즈.
   커밋 전 삭제하거나 `.gitignore` 에 추가 권장.
3. 전역 import 를 원하면 별도 카드로 `__init__.py` 추가 검토.
