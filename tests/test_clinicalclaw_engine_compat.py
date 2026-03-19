from __future__ import annotations

import importlib


def test_top_level_clinicalclaw_exports_create_claw_agent():
    from clinicalclaw import create_claw_agent as top_level_factory
    from clinicalclaw.engine import create_claw_agent as engine_factory

    assert top_level_factory is engine_factory


def test_clinicalclaw_engine_import_exposes_create_claw_agent():
    engine = importlib.import_module("clinicalclaw.engine")

    assert hasattr(engine, "create_claw_agent")
    assert callable(engine.create_claw_agent)


def test_clinicalclaw_engine_key_submodule_aliases_import():
    llm_module = importlib.import_module("clinicalclaw.engine.providers.llm")
    gateway_module = importlib.import_module("clinicalclaw.engine.gateway.server")

    assert hasattr(llm_module, "LLMProvider")
    assert hasattr(gateway_module, "create_app")


def test_clinicalclaw_top_level_main_delegates_to_engine_main():
    top_level_main = importlib.import_module("clinicalclaw.__main__")
    engine_main = importlib.import_module("clinicalclaw.engine.__main__")

    assert top_level_main.main is engine_main.main


def test_clinicalclaw_engine_exports_eventkind():
    engine = importlib.import_module("clinicalclaw.engine")

    assert hasattr(engine, "EventKind")
