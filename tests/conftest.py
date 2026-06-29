# Exclusion for standalone scripts — not pytest tests
collect_ignore = [
    "acceptance_test.py",
    "test_memory_suite.py.integration",
]
# Deprecated files
collect_ignore.extend([
    f for f in __import__("os").listdir(
        __import__("os").path.dirname(__file__)
    ) if f.endswith(".deprecated") or f.endswith(".integration")
])
