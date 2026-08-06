"""Tests for memory injection + self-improvement prompt rules (Task 6.4/6.8)."""
from eaccode.agent.context import build_system_prompt


def test_memory_injected_into_system_prompt():
    facts = ["Der Build nutzt uv", "Tests: pytest -x"]
    prompt = build_system_prompt(project_rules="", memory_facts=facts, skills="", workdir="/tmp")
    assert "Der Build nutzt uv" in prompt
    assert "[memory]" in prompt  # Quellen-Markierung


def test_memory_section_omitted_when_empty():
    prompt = build_system_prompt(project_rules="", memory_facts=[], skills="", workdir="/tmp")
    assert "[memory]" not in prompt


def test_rules_and_memory_separated():
    prompt = build_system_prompt(
        project_rules="REGLEN", memory_facts=["FAKT"], skills="", workdir="/tmp"
    )
    assert "REGLEN" in prompt
    assert "FAKT" in prompt


def test_self_improvement_rules_present():
    prompt = build_system_prompt(project_rules="", memory_facts=[], skills="", workdir="/tmp")
    assert "skill_create" in prompt or "Save the approach" in prompt
    assert "patch it immediately" in prompt.lower() or "skill_patch" in prompt


def test_skills_section_included():
    prompt = build_system_prompt(
        project_rules="", memory_facts=[], skills="# Available Skills\n- git: x",
        workdir="/tmp",
    )
    assert "Available Skills" in prompt
