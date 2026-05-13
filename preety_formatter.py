from typing import List, Dict, Any


class PrettySearchFormatter:
    """
    Turns raw embedding search results into LinkedIn-ready output.
    Focus: insight over raw logs.
    """

    def __init__(self, top_k: int = 10):
        self.top_k = top_k

    def format(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        results: list of dicts with:
            - score
            - symbol
            - type
            - file_path
            - optional code
        """

        lines = []

        # HEADER
        lines.append("\n" + "=" * 70)
        lines.append("SEMANTIC CODE SEARCH RESULTS")
        lines.append("=" * 70)

        # QUERY SECTION
        lines.append("\nQuery:")
        lines.append(f"   \"{query}\"\n")

        # TOP RESULTS (clean)
        lines.append("Top matches:\n")

        for i, r in enumerate(results[: self.top_k], 1):
            symbol = r.get("symbol", "-")
            score = r.get("score", 0.0)
            file_path = r.get("file_path", "-")

            lines.append(f"{i}. {symbol}")
            lines.append(f"   score: {score:.3f}")
            lines.append(f"   file : {self._shorten_path(file_path)}")
            lines.append("")

        # INSIGHT SECTION
        lines.append("Insight:")
        lines.append(self._generate_insight(results))

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)

    def _shorten_path(self, path: str, max_len: int = 60) -> str:
        if len(path) <= max_len:
            return path
        return "..." + path[-max_len:]

    def _generate_insight(self, results: List[Dict[str, Any]]) -> str:
        """
        Simple heuristic summarization.
        (You can later upgrade this with LLM or graph clustering)
        """

        keywords = []
        for r in results[:5]:
            symbol = r.get("symbol", "")
            if symbol:
                keywords.append(symbol.split(".")[-1])

        if not keywords:
            return "No dominant pattern detected."

        return (
            "The system clusters around:\n"
            f" • {keywords[0]}\n"
            f" • {keywords[1] if len(keywords) > 1 else ''}\n"
            f" • {keywords[2] if len(keywords) > 2 else ''}\n"
            "\nThis suggests the query maps to a coherent execution flow in the codebase."
        )