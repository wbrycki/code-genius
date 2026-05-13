import re
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

JAVA_KEYWORDS = {
    "if", "for", "while", "switch", "catch", "return", "new", "throw",
    "try", "else", "do", "synchronized", "super", "this",
}

# -----------------------------
# TREE-SITTER SETUP
# -----------------------------

JAVA_LANGUAGE = Language(tsjava.language())
parser = Parser(JAVA_LANGUAGE)


# -----------------------------
# HELPERS
# -----------------------------

def _strip_license_headers(code: str) -> str:
    """
    Remove common license headers at the top of files.
    """

    text = code

    m = re.match(r"^\s*/\*(.*?)\*/\s*", text, flags=re.DOTALL)

    if m:
        header = m.group(1).lower()

        if (
            "apache software foundation" in header
            or "licensed to the apache" in header
            or "license" in header
            or "copyright" in header
        ):
            text = text[m.end():]

    return text


def clean_for_embedding(code: str) -> str:
    """
    Remove package/import boilerplate before embeddings.
    """

    lines = code.splitlines()

    filtered = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("import "):
            continue

        if stripped.startswith("package "):
            continue

        filtered.append(line)

    return "\n".join(filtered)


def get_node_text(code: str, node):
    return code[node.start_byte:node.end_byte]


def extract_package_name(code: str):
    m = re.search(
        r'^\s*package\s+([\w\.]+)\s*;',
        code,
        flags=re.MULTILINE
    )

    return m.group(1) if m else None


# -----------------------------
# AST UTILITIES
# -----------------------------

def walk(node):
    yield node

    for child in node.children:
        yield from walk(child)


def find_method_calls(node, code):
    """
    Extract method invocations INSIDE a method body.
    """

    calls = []

    for child in walk(node):

        if child.type == "method_invocation":

            name_node = child.child_by_field_name("name")

            if name_node:
                method_name = get_node_text(code, name_node)

                if method_name not in JAVA_KEYWORDS:
                    calls.append(method_name)

    return list(set(calls))


# -----------------------------
# MAIN EXTRACTION
# -----------------------------

def extract_classes_and_methods(file_path):

    fragments = []

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()

    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return fragments

    code = _strip_license_headers(code)

    package_name = extract_package_name(code)

    tree = parser.parse(bytes(code, "utf8"))

    root = tree.root_node

    current_class = None

    for node in walk(root):

        # ---------------------------------
        # CLASS EXTRACTION
        # ---------------------------------

        if node.type == "class_declaration":

            class_name_node = node.child_by_field_name("name")

            if not class_name_node:
                continue

            class_name = get_node_text(code, class_name_node)

            current_class = class_name

            fq_class = (
                f"{package_name}.{class_name}"
                if package_name
                else class_name
            )

            class_code = get_node_text(code, node)

            fragments.append({
                "type": "class",
                "symbol": fq_class,
                "file_path": file_path,
                "code": clean_for_embedding(class_code),
                "calls": [],
            })

        # ---------------------------------
        # METHOD EXTRACTION
        # ---------------------------------

        elif node.type == "method_declaration":

            method_name_node = node.child_by_field_name("name")

            if not method_name_node:
                continue

            method_name = get_node_text(code, method_name_node)

            method_code = get_node_text(code, node)

            method_calls = find_method_calls(node, code)

            if current_class:
                fq_method = (
                    f"{package_name}.{current_class}.{method_name}"
                    if package_name
                    else f"{current_class}.{method_name}"
                )
            else:
                fq_method = method_name

            fragments.append({
                "type": "method",
                "symbol": fq_method,
                "file_path": file_path,
                "code": clean_for_embedding(method_code),
                "calls": method_calls,
            })

    return fragments