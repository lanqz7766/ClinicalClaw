from __future__ import annotations

import importlib
import sys

from clawagents import (  # noqa: E402
    ClawAgent,
    create_claw_agent,
    AgentState,
    OnEvent,
    EventKind,
    BeforeLLMHook,
    BeforeToolHook,
    AfterToolHook,
    TrajectoryRecorder,
    TurnRecord,
    RunSummary,
    extract_lessons,
    save_lessons,
    load_lessons,
    build_lesson_preamble,
    build_rethink_with_lessons,
    ContextEngine,
    ContextEngineConfig,
    DefaultContextEngine,
    register_context_engine,
    resolve_context_engine,
    list_context_engines,
    ChannelMessage,
    ChannelAdapter,
    ChannelRouter,
    KeyedAsyncQueue,
)

_PACKAGE_ALIASES = (
    "channels",
    "config",
    "context",
    "gateway",
    "graph",
    "logging",
    "memory",
    "process",
    "providers",
    "sandbox",
    "tools",
    "trajectory",
)

_MODULE_ALIASES = (
    "agent",
    "tokenizer",
    "channels.auto",
    "channels.keyed_queue",
    "channels.router",
    "channels.signal",
    "channels.telegram",
    "channels.types",
    "channels.whatsapp",
    "config.config",
    "context.engine",
    "gateway.protocol",
    "gateway.server",
    "gateway.ws",
    "graph.agent_loop",
    "logging.diagnostic",
    "memory.compaction",
    "memory.loader",
    "process.command_queue",
    "process.lanes",
    "providers.llm",
    "sandbox.backend",
    "sandbox.local",
    "sandbox.memory",
    "tools.advanced_fs",
    "tools.cache",
    "tools.compose",
    "tools.exec",
    "tools.filesystem",
    "tools.interactive",
    "tools.registry",
    "tools.skills",
    "tools.subagent",
    "tools.think",
    "tools.todolist",
    "tools.validate",
    "tools.web",
    "trajectory.compare",
    "trajectory.judge",
    "trajectory.lessons",
    "trajectory.recorder",
    "trajectory.verifier",
)


def _alias(alias_name: str, target_name: str):
    module = importlib.import_module(target_name)
    sys.modules.setdefault(alias_name, module)
    return module


for package_name in _PACKAGE_ALIASES:
    _alias(f"{__name__}.{package_name}", f"clawagents.{package_name}")

for module_name in _MODULE_ALIASES:
    _alias(f"{__name__}.{module_name}", f"clawagents.{module_name}")

__all__ = [
    "ClawAgent",
    "create_claw_agent",
    "AgentState",
    "OnEvent",
    "EventKind",
    "BeforeLLMHook",
    "BeforeToolHook",
    "AfterToolHook",
    "TrajectoryRecorder",
    "TurnRecord",
    "RunSummary",
    "extract_lessons",
    "save_lessons",
    "load_lessons",
    "build_lesson_preamble",
    "build_rethink_with_lessons",
    "ContextEngine",
    "ContextEngineConfig",
    "DefaultContextEngine",
    "register_context_engine",
    "resolve_context_engine",
    "list_context_engines",
    "ChannelMessage",
    "ChannelAdapter",
    "ChannelRouter",
    "KeyedAsyncQueue",
]
