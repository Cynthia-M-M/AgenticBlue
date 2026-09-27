"""
Backend scanner — uses Python AST to extract FastAPI routes and Pydantic fields.

No runtime import of the target project. AST-only.
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.analyzer.contracts import FieldDef, RouteContract

log = logging.getLogger("contractflow.scanner.backend")

# HTTP method decorator names we recognise
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _extract_decorator_route(decorator: ast.expr) -> Optional[Tuple[str, str]]:
    """
    Given a decorator node, return (method, path) if it looks like
    @app.post("/foo") or @router.get("/bar"), else None.
    """
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None
    method = func.attr.lower()
    if method not in _HTTP_METHODS:
        return None
    # Extract path — first positional arg or keyword arg "path"
    path: Optional[str] = None
    if decorator.args:
        arg = decorator.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            path = arg.value
    if path is None:
        for kw in decorator.keywords:
            if kw.arg == "path" and isinstance(kw.value, ast.Constant):
                path = kw.value.value
                break
    if path is None:
        return None
    return method.upper(), path


def _get_body_schema_name(func_def: ast.FunctionDef) -> Optional[str]:
    """
    Return the type annotation name of the first parameter that looks like
    a Pydantic body model (not 'self', not basic types, not Request/Response).
    """
    _skip = {"self", "cls", "request", "response", "db", "session", "background_tasks"}
    _primitives = {"int", "str", "float", "bool", "bytes", "None"}

    for arg in func_def.args.args:
        if arg.arg in _skip:
            continue
        ann = arg.annotation
        if ann is None:
            continue
        # Plain Name node: def foo(appointment: AppointmentCreate)
        if isinstance(ann, ast.Name) and ann.id not in _primitives:
            return ann.id
        # Attribute node: def foo(appointment: schemas.AppointmentCreate)
        if isinstance(ann, ast.Attribute):
            return ann.attr
    return None


def _parse_pydantic_model(
    tree: ast.Module, model_name: str, source_file: str
) -> List[FieldDef]:
    """
    Walk the AST tree looking for a class named model_name that inherits
    from BaseModel (or any base), and return its annotated fields.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name != model_name:
            continue
        fields: List[FieldDef] = []
        for item in node.body:
            # Pydantic fields are annotated assignments: field: type [= default]
            if isinstance(item, ast.AnnAssign) and isinstance(
                item.target, ast.Name
            ):
                field_name = item.target.id
                if field_name.startswith("_"):
                    continue
                # Stringify the annotation
                try:
                    type_str = ast.unparse(item.annotation)
                except Exception:
                    type_str = "unknown"
                fields.append(FieldDef(name=field_name, type_annotation=type_str))
        return fields
    return []


def scan_backend(directory: Path) -> List[RouteContract]:
    """
    Scan all .py files under `directory` for FastAPI routes and their
    Pydantic request body schemas.

    Returns a list of RouteContract objects.
    """
    directory = Path(directory)
    contracts: List[RouteContract] = []

    # First pass: collect all model definitions across all files
    model_registry: Dict[str, Tuple[List[FieldDef], str]] = {}  # name → (fields, file)
    for py_file in sorted(directory.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            log.warning("scan_backend: syntax error in %s — %s", py_file, exc)
            continue
        except OSError as exc:
            log.warning("scan_backend: cannot read %s — %s", py_file, exc)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Collect any class that has annotated fields (could be Pydantic)
                fields = _parse_pydantic_model(tree, node.name, str(py_file))
                if fields:
                    rel = str(py_file.relative_to(directory))
                    model_registry[node.name] = (fields, rel)

    log.info("scan_backend: %d model(s) found in registry", len(model_registry))

    # Second pass: find route decorators and match schemas
    for py_file in sorted(directory.rglob("*.py")):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            log.warning("scan_backend: syntax error in %s — %s", py_file, exc)
            continue
        except OSError as exc:
            log.warning("scan_backend: cannot read %s — %s", py_file, exc)
            continue

        rel_file = str(py_file.relative_to(directory))

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                route = _extract_decorator_route(decorator)
                if route is None:
                    continue
                method, path = route
                schema_name = _get_body_schema_name(node)
                fields: List[FieldDef] = []
                if schema_name and schema_name in model_registry:
                    fields, _ = model_registry[schema_name]

                contracts.append(
                    RouteContract(
                        method=method,
                        path=path,
                        schema_name=schema_name or "",
                        fields=fields,
                        file=rel_file,
                    )
                )

    log.info("scan_backend: %d route contract(s) extracted", len(contracts))
    return contracts


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("demo_project/backend")
    results = scan_backend(target)
    for r in results:
        print(r)
