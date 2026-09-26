from __future__ import annotations

import ast
import re
import subprocess
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOMENTUM_DIR = ROOT / "MomentumMatch"
MODULE_DIR = MOMENTUM_DIR / "modules"

EXPECTED_MODULES = (
    "01_runtime.py",
    "02_memory.py",
    "03_models.py",
    "04_engines.py",
    "05_chart_tv.py",
    "06_snapshot_core.py",
    "07_overlay_renderers.py",
    "08_scene_archive.py",
    "09_team_identity.py",
    "10_app_gui_snapshot.py",
    "12_selftest_entry.py",
)

PERSIAN_ARABIC_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")
HEX_RE = re.compile(r"^0[xX][0-9a-fA-F]+$")
BYTE_ESCAPE_RE = re.compile(r"\\x[0-9a-fA-F]{2}")


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def normalize_ast(node: ast.AST) -> ast.AST:
    class Normalizer(ast.NodeTransformer):
        def generic_visit(self, current):
            if isinstance(current, ast.Constant) and isinstance(current.value, str):
                return ast.copy_location(ast.Constant(value="__STRING_LITERAL__"), current)
            return super().generic_visit(current)

    normalized = Normalizer().visit(node)
    ast.fix_missing_locations(normalized)
    return normalized


def collect_symbols(tree: ast.AST) -> set[str]:
    result: set[str] = set()

    def add_target(target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            result.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                add_target(item)
        elif isinstance(target, ast.Starred):
            add_target(target.value)

    class Collector(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            result.add(node.name)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            result.add(node.name)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            result.add(node.name)
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                result.add(alias.asname or alias.name.split(".")[0])

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                if alias.name != "*":
                    result.add(alias.asname or alias.name)

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                add_target(target)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            add_target(node.target)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            add_target(node.target)

    Collector().visit(tree)
    return result


def collect_sensitive_literals(source: str) -> set[str]:
    result: set[str] = set()
    tokens = tokenize.generate_tokens(iter(source.splitlines(True)).__next__)
    for token in tokens:
        if token.type == tokenize.NUMBER and HEX_RE.fullmatch(token.string):
            value = token.string.lower()
            if int(value, 16) >= 0x100:
                result.add(value)
        elif token.type == tokenize.STRING:
            result.update(BYTE_ESCAPE_RE.findall(token.string))
    return result


def collect_persian_logic_strings(tree: ast.AST) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []

    class Finder(ast.NodeVisitor):
        def __init__(self) -> None:
            self.parents: list[ast.AST] = []

        def visit(self, node: ast.AST) -> None:
            self.parents.append(node)
            super().visit(node)
            self.parents.pop()

        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str) and PERSIAN_ARABIC_RE.search(node.value):
                parent = self.parents[-2] if len(self.parents) >= 2 else None
                if isinstance(
                    parent,
                    (
                        ast.Compare,
                        ast.Subscript,
                        ast.Dict,
                        ast.Set,
                        ast.MatchValue,
                        ast.MatchClass,
                        ast.JoinedStr,
                    ),
                ):
                    preview = re.sub(r"\s+", " ", node.value).strip()
                    findings.append((getattr(node, "lineno", 0), preview[:120]))

    Finder().visit(tree)
    return findings


def load_original() -> str:
    return run_git("show", "origin/main:MomentumMatch/MomentumMod.py")


def load_modular_source() -> str:
    chunks = []
    for name in EXPECTED_MODULES:
        path = MODULE_DIR / name
        if not path.is_file():
            raise AssertionError(f"Missing Momentum module: {path}")
        chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def main() -> None:
    if (MODULE_DIR / "11_app_runtime.py").exists():
        raise AssertionError("Stale module 11_app_runtime.py still exists; App runtime must remain in module 10.")

    loader = (MOMENTUM_DIR / "MomentumMod.py").read_text(encoding="utf-8")
    for name in EXPECTED_MODULES:
        if f'"{name}"' not in loader:
            raise AssertionError(f"{name} is missing from MomentumMod.py loader.")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "11_app_runtime.py" in readme:
        raise AssertionError("README still documents removed 11_app_runtime.py.")
    if "Python Library Downloader.py" in readme:
        raise AssertionError("README contains the wrong downloader filename.")

    modular_source = load_modular_source()
    original_source = load_original()

    original_tree = ast.parse(original_source, filename="MomentumMod.py")
    current_bodies: list[ast.stmt] = []
    for name in EXPECTED_MODULES:
        tree = ast.parse((MODULE_DIR / name).read_text(encoding="utf-8"), filename=name)
        current_bodies.extend(tree.body)

    current_tree = ast.Module(body=current_bodies, type_ignores=[])

    original_normalized = ast.dump(normalize_ast(original_tree), include_attributes=False)
    current_normalized = ast.dump(normalize_ast(current_tree), include_attributes=False)
    if original_normalized != current_normalized:
        raise AssertionError(
            "The modular Momentum source does not match the original monolith AST "
            "after ignoring string literal contents. This indicates a code-structure change."
        )

    original_symbols = collect_symbols(original_tree)
    current_symbols = collect_symbols(current_tree)
    missing = sorted(original_symbols - current_symbols)
    if missing:
        raise AssertionError(f"Runtime symbols missing after refactor: {missing[:40]}")

    original_literals = collect_sensitive_literals(original_source)
    current_literals = collect_sensitive_literals(modular_source)
    missing_literals = sorted(original_literals - current_literals)
    if missing_literals:
        raise AssertionError(
            "Sensitive hex/byte literals disappeared during refactor: "
            + ", ".join(missing_literals[:80])
        )

    all_python = sorted(ROOT.rglob("*.py"))
    non_english_files: list[str] = []
    for path in all_python:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if PERSIAN_ARABIC_RE.search(content):
            non_english_files.append(str(path.relative_to(ROOT)))
    if non_english_files:
        raise AssertionError("Persian/Arabic-script source text remains in: " + ", ".join(non_english_files))

    requirements = {
        line.strip().lower()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    downloader_source = (ROOT / "Python_Library_Downloader.py").read_text(encoding="utf-8")
    downloader_tree = ast.parse(downloader_source, filename="Python_Library_Downloader.py")
    package_node = next(
        (
            node
            for node in downloader_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "REQUIRED_PACKAGES" for target in node.targets)
        ),
        None,
    )
    if package_node is None:
        raise AssertionError("REQUIRED_PACKAGES was not found in Python_Library_Downloader.py.")
    downloader_packages = {
        str(item[0]).lower()
        for item in ast.literal_eval(package_node.value)
        if isinstance(item, (tuple, list))
        and len(item) >= 1
        and isinstance(item[0], ast.Constant)
        and isinstance(item[0].value, str)
        and item[0].value.lower() != "pyinstaller"
    }
    missing_deps = sorted(requirements - downloader_packages)
    if missing_deps:
        raise AssertionError(
            "requirements.txt contains packages not represented by REQUIRED_PACKAGES: "
            + ", ".join(missing_deps)
        )

    logic_strings = collect_persian_logic_strings(original_tree)
    if logic_strings:
        print("Warning: Persian strings originally appeared in logic-sensitive AST contexts:")
        for line, value in logic_strings[:40]:
            print(f"  line {line}: {value}")

    print("Momentum refactor structural verification: PASS")
    print(f"  Original AST symbols: {len(original_symbols)}")
    print(f"  Modular AST symbols: {len(current_symbols)}")
    print(f"  Sensitive hex/byte literals preserved: {len(original_literals)}")
    print(f"  Python files checked for Persian/Arabic text: {len(all_python)}")


if __name__ == "__main__":
    main()
