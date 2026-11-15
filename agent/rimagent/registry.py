"""Tool registry: built-in tools, bridge-generated tools, and hot-loaded brain tools.

A tool is a Python callable `fn(ctx, **kwargs) -> Any`. `ctx` is the Context (bridge, llm, brain helpers, emit).
The registry produces OpenAI tool specs and executes calls with error capture.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
import traceback
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .paths import TOOLS, WATCHERS

_TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}

RESERVED_GROUPS: set[str] = {"watchdog"}


def _schema_from_signature(fn: Callable) -> dict[str, Any]:
    sig = inspect.signature(fn)
    hints = typing.get_type_hints(fn) if hasattr(fn, "__annotations__") else {}
    props: dict[str, Any] = {}
    required: list[str] = []
    for name, p in sig.parameters.items():
        if name == "ctx" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        t = hints.get(name, str)
        origin = typing.get_origin(t)
        if origin is typing.Union or (origin is not None and str(origin) == "<class 'types.UnionType'>"):
            args = [a for a in typing.get_args(t) if a is not type(None)]
            t = args[0] if args else str
            origin = typing.get_origin(t)
        js: dict[str, Any]
        if origin in (list, typing.List):
            js = {"type": "array"}
        elif origin in (dict, typing.Dict):
            js = {"type": "object"}
        else:
            js = {"type": _TYPE_MAP.get(t, "string")}
        doc = getattr(fn, "_param_docs", {}).get(name)
        if doc:
            js["description"] = doc
        props[name] = js
        if p.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": props, "required": required}


@dataclass
class Tool:
    name: str
    description: str
    fn: Callable
    schema: dict[str, Any]
    source: str = "builtin"
    group: str = "general"

    def spec(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description[:1024], "parameters": self.schema}}


def tool(name: str | None = None, description: str | None = None, params: dict[str, str] | None = None, group: str = "general", **aliases: dict[str, str]):
    if params is None:
        for alt in ("args", "arguments", "argdocs", "parameters"):
            if alt in aliases:
                params = aliases.pop(alt)
                break
    if aliases:
        raise TypeError(f"tool() got unexpected keyword argument(s): {', '.join(aliases)}")

    def deco(fn: Callable) -> Callable:
        fn._tool_name = name or fn.__name__
        fn._tool_desc = description or (fn.__doc__ or "").strip()
        fn._param_docs = params or {}
        fn._tool_group = group
        return fn

    return deco


@dataclass
class Registry:
    tools: dict[str, Tool] = field(default_factory=dict)
    load_errors: dict[str, str] = field(default_factory=dict)
    _mtimes: dict[str, float] = field(default_factory=dict)
    watchers: dict[str, Callable] = field(default_factory=dict)
    watcher_errors: dict[str, str] = field(default_factory=dict)
    watcher_superseded: dict[str, str] = field(default_factory=dict)
    watcher_kept: set[str] = field(default_factory=set)

    def add(self, fn: Callable, source: str = "builtin") -> Tool:
        name = getattr(fn, "_tool_name", fn.__name__)
        t = Tool(name=name, description=getattr(fn, "_tool_desc", ""), fn=fn, schema=_schema_from_signature(fn), source=source, group=getattr(fn, "_tool_group", "general"))
        self.tools[name] = t
        return t

    def add_module(self, module: Any, source: str = "builtin") -> list[str]:
        names = []
        for _, obj in inspect.getmembers(module, inspect.isfunction):
            if hasattr(obj, "_tool_name"):
                self.add(obj, source)
                names.append(obj._tool_name)
        return names

    def add_bridge_methods(self, methods: list[dict[str, str]]) -> None:
        for m in methods:
            method = m["method"]
            name = "rw_" + method.replace(".", "_")
            doc = m.get("doc", "")

            def make(method_name: str):
                def fn(ctx, **params):
                    params = {k: coerce_param(v) for k, v in params.items()}

                    # 💡 Auto-Correct Research Names
                    if method_name == "steward.research":
                        queue = params.get("queue", [])
                        if queue:
                            try:
                                corrected = []
                                for research_name in queue:
                                    try:
                                        results = ctx.bridge.call("defs.search", query=research_name, type="ResearchProjectDef")
                                        if results and isinstance(results, list) and len(results) > 0:
                                            corrected.append(results[0].get("def", research_name))
                                        else:
                                            corrected.append(research_name)
                                    except Exception:
                                        corrected.append(research_name)
                                if corrected != queue:
                                    params["queue"] = corrected
                            except Exception:
                                pass

                    # 💡 Auto-Correct Build Def Names + Stuff (สำหรับ ui.build)
                    if method_name == "ui.build" and "def" in params:
                        def_name = params["def"]
                        
                        # 💡 Auto-Correct Sandbag (Sandbag_TurretBase -> Sandbags)
                        if def_name in ("Sandbag_TurretBase", "Sandbags"):
                            params["def"] = "Sandbags"
                            if params.get("stuff") == "Steel":
                                params["stuff"] = "Cloth"
                        else:
                            base = None
                            if "_" in def_name:
                                base = def_name.split("_")[0]  # "Wall_Stone" -> "Wall"
                            elif def_name.endswith(("Wood", "Stone", "Steel")):
                                for suffix in ("Wood", "Stone", "Steel"):
                                    if def_name.endswith(suffix):
                                        base = def_name[:-len(suffix)]  # "WallWood" -> "Wall"
                                        break
                            if base:
                                try:
                                    results = ctx.bridge.call("defs.search", query=base, type="ThingDef")
                                    if results and isinstance(results, list) and len(results) > 0:
                                        corrected_def = results[0].get("def", def_name)
                                        if corrected_def != def_name:
                                            params["def"] = corrected_def
                                            if corrected_def in ("Wall", "Door") and "stuff" not in params:
                                                stocks = ctx.bridge.call("state.summary").get("key_stocks", {})
                                                if stocks.get("WoodLog", 0) > 100:
                                                    params["stuff"] = "WoodLog"
                                                elif stocks.get("BlocksSandstone", 0) > 50:
                                                    params["stuff"] = "BlocksSandstone"
                                                elif stocks.get("Steel", 0) > 100:
                                                    params["stuff"] = "Steel"
                                except Exception:
                                    pass

                    # 💡 Auto-Correct Build Def Names + Stuff (สำหรับ ui.build_many)
                    if method_name == "ui.build_many" and "ops" in params:
                        for op in params["ops"]:
                            if "def" in op:
                                def_name = op["def"]
                                if def_name in ("Sandbag_TurretBase", "Sandbags"):
                                    op["def"] = "Sandbags"
                                    if op.get("stuff") == "Steel":
                                        op["stuff"] = "Cloth"
                                else:
                                    base = None
                                    if "_" in def_name:
                                        base = def_name.split("_")[0]
                                    elif def_name.endswith(("Wood", "Stone", "Steel")):
                                        for suffix in ("Wood", "Stone", "Steel"):
                                            if def_name.endswith(suffix):
                                                base = def_name[:-len(suffix)]
                                                break
                                    if base:
                                        try:
                                            results = ctx.bridge.call("defs.search", query=base, type="ThingDef")
                                            if results and isinstance(results, list) and len(results) > 0:
                                                corrected_def = results[0].get("def", def_name)
                                                if corrected_def != def_name:
                                                    op["def"] = corrected_def
                                                    if corrected_def in ("Wall", "Door") and "stuff" not in op:
                                                        stocks = ctx.bridge.call("state.summary").get("key_stocks", {})
                                                        if stocks.get("WoodLog", 0) > 100:
                                                            op["stuff"] = "WoodLog"
                                                        elif stocks.get("BlocksSandstone", 0) > 50:
                                                            op["stuff"] = "BlocksSandstone"
                                                        elif stocks.get("Steel", 0) > 100:
                                                            op["stuff"] = "Steel"
                                        except Exception:
                                            pass

                    # 💡 Auto-Correct Thing ID (สำหรับ ui.add_bill)
                    if method_name == "ui.add_bill" and "thing" in params:
                        thing_val = params["thing"]
                        if isinstance(thing_val, str) and not thing_val[0].isdigit():
                            try:
                                results = ctx.bridge.call("map.find", **{"kind": "building", "def": thing_val})
                                if results and isinstance(results, list) and len(results) > 0:
                                    params["thing"] = results[0].get("id", thing_val)
                            except Exception:
                                pass

                    # 💡 dry_run สำหรับ ui.build
                    if method_name == "ui.build" and not params.get("dry_run", False):
                        dry_params = {**params, "dry_run": True}
                        try:
                            dry_result = ctx.bridge.call(method_name, **dry_params)
                            if dry_result.get("failed"):
                                return {
                                    "error": "Cell is occupied or blocked. Choose a different cell.",
                                    "failed": dry_result.get("failed"),
                                    "camera": dry_result.get("camera")
                                }
                        except Exception:
                            pass

                    # 💡 dry_run สำหรับ ui.zone
                    if method_name == "ui.zone" and params.get("action") in ("create_stockpile", "create_growing"):
                        cells = params.get("cells", [])
                        rect = params.get("rect")
                        if rect:
                            x, z, w, h = rect
                            cells = [[x + i, z + j] for i in range(w) for j in range(h)]
                        if cells:
                            try:
                                occupied = []
                                for cell in cells[:10]:
                                    detail = ctx.bridge.call("map.cell", cell=cell)
                                    if detail.get("thing") or detail.get("building"):
                                        occupied.append(cell)
                                if occupied:
                                    return {
                                        "error": f"Cells are occupied: {occupied[:3]}... Choose a different area.",
                                        "occupied": occupied
                                    }
                            except Exception:
                                pass

                    result = ctx.bridge.call(method_name, **params)
                    if method_name in ("game.speed", "game.pause"):
                        ctx.extra["model_speed"] = 0 if (method_name == "game.pause" and params.get("paused", True)) else int(params.get("speed", 1) if method_name == "game.speed" else ctx.extra.get("model_speed", 1))
                    return result
                return fn

            self.tools[name] = Tool(
                name=name,
                description=f"[RimBridge {method}] {doc}",
                fn=make(method),
                schema={"type": "object", "properties": {}, "additionalProperties": True, "description": "params as described: " + doc[:600]},
                source="bridge",
                group=method.split(".")[0],
            )
        self.annotate_bridge_docs()

    def annotate_bridge_docs(self, notes: dict[str, str] | None = None) -> None:
        for method, note in (notes or BRIDGE_DOC_NOTES).items():
            t = self.tools.get("rw_" + method.replace(".", "_"))
            if t is None or t.source != "bridge" or note in t.description:
                continue
            t.description = (t.description.rstrip() + " " + note).strip()
            t.schema = {**t.schema, "description": (t.schema.get("description", "") + " " + note)[:900]}

    def reload_brain(self) -> None:
        for path in sorted(TOOLS.glob("*.py")):
            self._load_file(path, kind="tool")
        for path in sorted(WATCHERS.glob("*.py")):
            self._load_file(path, kind="watcher")
        live = {p.stem for p in TOOLS.glob("*.py")}
        for name, t in list(self.tools.items()):
            if t.source == "brain" and getattr(t.fn, "_brain_file", None) not in live:
                del self.tools[name]
        live_w = {p.stem for p in WATCHERS.glob("*.py")}
        for name in list(self.watchers):
            if name not in live_w:
                del self.watchers[name]
        for name in list(self.watcher_superseded):
            if name not in live_w:
                del self.watcher_superseded[name]

    def _load_file(self, path: Path, kind: str) -> None:
        key = f"{kind}:{path.name}"
        mtime = path.stat().st_mtime
        if self._mtimes.get(key) == mtime:
            return
        self._mtimes[key] = mtime
        modname = f"brain_{kind}_{re.sub(r'[^a-zA-Z0-9_]', '_', path.stem)}"
        try:
            spec = importlib.util.spec_from_file_location(modname, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[modname] = mod
            spec.loader.exec_module(mod)
        except Exception:
            err = traceback.format_exc(limit=3)
            (self.load_errors if kind == "tool" else self.watcher_errors)[path.name] = err
            return
        (self.load_errors if kind == "tool" else self.watcher_errors).pop(path.name, None)
        if kind == "tool":
            for name, t in list(self.tools.items()):
                if t.source == "brain" and getattr(t.fn, "_brain_file", None) == path.stem:
                    del self.tools[name]
            for _, obj in inspect.getmembers(mod, inspect.isfunction):
                if hasattr(obj, "_tool_name"):
                    obj._brain_file = path.stem
                    self.add(obj, source="brain")
        else:
            fn = getattr(mod, "watch", None)
            if callable(fn):
                self.watchers[path.stem] = fn
            else:
                self.watcher_errors[path.name] = "no watch(ctx, events) function"

    def set_superseded(self, mapping: dict[str, str]) -> dict[str, str]:
        self.watcher_superseded = {str(k): str(v) for k, v in (mapping or {}).items() if k and k not in self.watcher_kept}
        return self.watcher_superseded

    def release_watcher(self, stem: str) -> None:
        self.watcher_kept.add(stem)
        self.watcher_superseded.pop(stem, None)

    def specs(self, groups: set[str] | None = None, exclude: set[str] | None = None, allow: Callable[[Tool], bool] | None = None) -> list[dict[str, Any]]:
        out = []
        for t in self.tools.values():
            if t.group in RESERVED_GROUPS and not (groups and t.group in groups):
                continue
            if groups and t.group not in groups and t.source != "brain":
                continue
            if exclude and t.name in exclude:
                continue
            if allow is not None and not allow(t):
                continue
            out.append(t.spec())
        return out

    def execute(self, ctx: Any, name: str, args: dict[str, Any]) -> tuple[Any, bool]:
        t = self.tools.get(name)
        if t is None:
            return {"error": f"unknown tool {name!r}"}, False
        try:
            if t.source == "bridge":
                return t.fn(ctx, **args), True
            args = {k: coerce_param(v) if k not in ("code", "body", "text", "content") else v for k, v in args.items()}
            sig = inspect.signature(t.fn)
            accepts_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
            if not accepts_kwargs:
                args = remap_params(sig, args)
                unknown = [k for k in args if k not in sig.parameters]
                if unknown:
                    return {"error": f"unknown parameter(s) {unknown} for {name}; accepted: {[p for p in sig.parameters if p != 'ctx']}"}, False
            return t.fn(ctx, **args), True
        except Exception as e:
            tb = traceback.format_exc(limit=4)
            return {"error": f"{type(e).__name__}: {e}", "trace": tb[-1200:] if t.source == "brain" else None}, False


BRIDGE_DOC_NOTES: dict[str, str] = {
    "ui.set_work": "NOTE: takes the pawn out of steward management (the steward stops setting its priorities until rw_steward_pawn managed=true); prefer rw_steward_posture for a temporary bias.",
    "ui.set_work_many": "NOTE: takes every listed pawn out of steward management (rw_steward_pawn managed=true hands one back); prefer rw_steward_posture for a temporary bias.",
    "ui.designate": "NOTE: the steward's stock jobs already designate trees/plants/animals/ore toward their targets; prefer rw_steward_stock_set (raise the target) over hand designation while that job is enabled. For a one-off tree use designator=cut (forestry adopts harvestwood designations and releases them when its target is met).",
    "ui.draft": "NOTE: the combat standing order drafts and positions colonists at the rally point by itself; a pawn you draft/move by hand is hands-off for that order for a while (rw_steward_orders_explain combat lists them). Prefer rw_steward_orders_rally to move everyone.",
    "ui.goto": "NOTE: a pawn you move by hand is hands-off for the combat standing order for a while; to move the whole defense set the rally rect with rw_steward_orders_rally.",
    "ui.attack": "NOTE: a pawn you order to attack by hand is hands-off for the combat standing order for a while; use it to override (breachers, sappers, drop pods inside), not for every fight.",
    "steward.settings": "NOTE: writes the RimBridge mod settings file, which persists across games and episodes (the notebook does not); prefer rw_steward_posture for a per-colony bias. A JSON null removes a globalWorkAdjustments key.",
}

_ALIASES = {"content": "text", "body": "text", "markdown": "text", "note": "text", "message": "text", "notes": "text", "filename": "file", "path": "file", "source": "code", "python": "code", "skill": "name", "title": "name", "query": "q"}


def remap_params(sig: inspect.Signature, args: dict[str, Any]) -> dict[str, Any]:
    params = [p for p in sig.parameters if p != "ctx"]
    out = dict(args)
    for k in list(out):
        if k not in params and k in _ALIASES and _ALIASES[k] in params and _ALIASES[k] not in out:
            out[_ALIASES[k]] = out.pop(k)
    unknown = [k for k in out if k not in params]
    missing = [p for p in params if p not in out and sig.parameters[p].default is inspect.Parameter.empty]
    if len(unknown) == 1 and len(missing) == 1:
        out[missing[0]] = out.pop(unknown[0])
    return out


def coerce_param(v: Any) -> Any:
    if isinstance(v, str):
        t = v.replace("\r", "").replace("\n", "").strip()
        if t and (t[0] in "[{" or t in ("true", "false", "null") or re.fullmatch(r"-?\d+(\.\d+)?", t)):
            try:
                return json.loads(t)
            except json.JSONDecodeError:
                return v
        if re.fullmatch(r"-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?", t):
            try:
                parts = [float(x.strip()) if "." in x else int(x.strip()) for x in t.split(",")]
                return parts
            except ValueError:
                return v
        return v
    if isinstance(v, list):
        return [coerce_param(x) for x in v]
    if isinstance(v, dict):
        return {k: coerce_param(x) for k, x in v.items()}
    return v


def to_text(result: Any, limit: int = 8000) -> str:
    if isinstance(result, str):
        s = result
    else:
        try:
            s = json.dumps(result, ensure_ascii=False, default=str)
        except Exception:
            s = str(result)
    if len(s) > limit:
        s = s[:limit] + f"\n…(truncated {len(s) - limit} chars; narrow the query)"
    return s