"""Marker so multi-file examples import as proper packages.

Single-file examples (build_an_agent, agent_idea_web) don't need this — but a
multi-module example like `inspiration_bot` does, so its modules can import each
other as `examples.inspiration_bot.<module>` under both `python -m ...` and
`fastapi run ...`.
"""
