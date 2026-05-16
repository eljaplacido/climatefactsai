"""Adversarial robustness probes — Phase 6 wave 3.

Tests in this package are marked `@pytest.mark.adversarial`. They run
in the normal pytest collection but can be selected/excluded with
`pytest -m adversarial` or `pytest -m "not adversarial"`.

Probes target real attack surface — hostile LLM outputs, malformed
JSON, degenerate inputs, SSRF redirect chains — and pin the behaviour
we want the platform to maintain. A failing probe surfaces a real gap;
treat it as a P0 to fix in the next session.
"""
