"""Pure helpers for portable COMPAS Masonry session files."""


def selected_results(stored, selection) -> dict:
    """Return only the selected ``(problem name, result key)`` pairs."""
    selected = {}
    for problem_name, result_key in selection:
        result = (stored.get(problem_name) or {}).get(result_key)
        if result is not None:
            selected.setdefault(problem_name, {})[result_key] = result
    return selected
