import ast
import builtins
import glob
import sys

builtin_names = set(dir(builtins))

def check_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        src = f.read()
    try:
        compile(src, filepath, 'exec')
    except Exception as e:
        print(f"[SYNTAX ERROR] {filepath}: {e}")
        return False

    tree = ast.parse(src, filename=filepath)
    defined = set(builtin_names)
    defined.add("__file__")
    defined.add("__name__")
    defined.add("__doc__")
    
    # Track imports, functions, classes, and top-level assigned variables
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                defined.add(n.asname or n.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for n in node.names:
                defined.add(n.asname or n.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            for arg in node.args.args:
                defined.add(arg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)

    # Now look for module usages like `<module>.<attr>` or `<func>(...)` where module is not defined
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if isinstance(node.value.ctx, ast.Load):
                if node.value.id not in defined:
                    errors.append((node.lineno, node.value.id))

    if errors:
        print(f"[POSSIBLE UNDEFINED IN] {filepath}:")
        for ln, name in sorted(set(errors)):
            print(f"   Line {ln}: '{name}' not found in defined imports/variables")
        return False
    return True

py_files = sorted(glob.glob('*.py') + glob.glob('core/*.py') + glob.glob('tests/*.py'))
any_failed = False
for p in py_files:
    if not check_file(p):
        any_failed = True

if not any_failed:
    print("[ALL CLEAN] All files passed static import and syntax verification!")
