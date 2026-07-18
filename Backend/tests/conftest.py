"""Shared test setup. Forces the LLM offline so the suite is deterministic and network-free
(coaching grading falls back to the heuristic grader). Tests that want the LLM path
monkeypatch lib.llm_client explicitly."""

import os

import pytest


@pytest.fixture(autouse=True)
def _offline_llm(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    yield
