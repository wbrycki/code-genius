import os
import re

JAVA_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "throw",
    "try", "else", "do", "synchronized", "super", "this", "eval",
    "String", "INT", "ROW", "FIELD", "FLOAT", "BOOLEAN", "explicit",
    "hashCode", "equals", "toString", "clone", "finalize", "wait",
    "notify", "notifyAll"
}

def _strip_license_headers(code: str) -> str:
    """Remove common license headers at the top of files (e.g., Apache ASF).
    We conservatively remove only the leading comment banner if it contains license/copyright terms.
    """
    text = code

    # Pattern 1: Leading block comment /* ... */
    m = re.match(r"^\s*/\*(.*?)\*/\s*", text, flags=re.DOTALL)
    if m:
        header = m.group(1)
        header_lower = header.lower()
        if ("apache software foundation" in header_lower or
            "licensed to the apache" in header_lower or
            "license" in header_lower or
            "copyright" in header_lower):
            text = text[m.end():]

    # Pattern 2: Leading line comments // ... until a blank line or code token
    # Only strip if it contains license keywords
    m2 = re.match(r"^\s*(?:(//.*?\n)+)\s*", text, flags=re.DOTALL)
    if m2:
        header = m2.group(0)
        if re.search(r"apache|license|copyright", header, flags=re.IGNORECASE):
            text = text[m2.end():]

    return text


def extract_classes_and_methods(file_path):
    """
    Extracts classes, methods, and filtered method calls from a Java file.
    
    Returns a list of fragments, each containing:
    - type: 'class' or 'method'
    - symbol: class or method name
    - code: full code of the file
    - calls: list of called methods inside that fragment
    """
    fragments = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return fragments

    # Strip license/comment banners to avoid storing boilerplate
    code = _strip_license_headers(code)

    # Extract package (if any)
    pkg_match = re.search(r'^\s*package\s+([\w\.]+)\s*;', code, flags=re.MULTILINE)
    package_name = pkg_match.group(1) if pkg_match else None

    # Extract classes
    classes = re.findall(r'class\s+(\w+)', code)
    if classes:
        print(f"  Found classes: {classes}")
    else:
        print(f"  No classes found in {file_path}")

    # Extract methods
    methods = re.findall(r'(public|protected|private).*?\s+(\w+)\s*\(.*?\)\s*{', code)
    method_names_set = set([m[1] for m in methods])
    if methods:
        print(f"  Found methods: {[m[1] for m in methods]}")
    else:
        print(f"  No methods found in {file_path}")

    # Extract calls
    calls = re.findall(r'(\w+)\s*\(', code)
    filtered_calls = [c for c in calls if c not in JAVA_KEYWORDS and c in method_names_set]
    if filtered_calls:
        print(f"  Found calls: {filtered_calls}")
    else:
        print(f"  No relevant calls found in {file_path}")

    # Build FQNs helper
    def fq_class(cls: str) -> str:
        return f"{package_name}.{cls}" if package_name else cls

    def fq_method(method: str, cls: str | None) -> str:
        if cls:
            base = f"{fq_class(cls)}.{method}"
        else:
            base = method if not package_name else f"{package_name}.{method}"
        return base

    # Precompute a naive mapping of method name -> FQN using the first class if available
    primary_class = classes[0] if classes else None
    method_fqn_map = {m: fq_method(m, primary_class) for m in method_names_set}

    # Build fragments for classes
    for cls in classes:
        fragments.append({
            "type": "class",
            "symbol": fq_class(cls),
            "file_path": file_path,
            "code": code,
            "calls": filtered_calls
        })

    # Build fragments for methods
    for _, method in methods:
        fragments.append({
            "type": "method",
            "symbol": method_fqn_map.get(method, method),
            "file_path": file_path,
            "code": code,
            # Map intra-file calls to FQN when we know them; leave external names as-is
            "calls": [method_fqn_map.get(c, c) for c in filtered_calls if c != method]
        })

    return fragments
