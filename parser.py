import os
import re

JAVA_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "throw",
    "try", "else", "do", "synchronized", "super", "this", "eval",
    "String", "INT", "ROW", "FIELD", "FLOAT", "BOOLEAN", "explicit",
    "hashCode", "equals", "toString", "clone", "finalize", "wait",
    "notify", "notifyAll"
}

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

    # Build fragments for classes
    for cls in classes:
        fragments.append({
            "type": "class",
            "symbol": cls,
            "code": code,
            "calls": filtered_calls
        })

    # Build fragments for methods
    for _, method in methods:
        fragments.append({
            "type": "method",
            "symbol": method,
            "code": code,
            "calls": [c for c in filtered_calls if c != method]
        })

    return fragments
