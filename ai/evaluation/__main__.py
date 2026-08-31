"""Run evaluation: python -m ai.evaluation"""
from .runner import run_evaluation

if __name__ == "__main__":
    import json, sys
    result = run_evaluation()
    print(json.dumps(result, indent=2))
