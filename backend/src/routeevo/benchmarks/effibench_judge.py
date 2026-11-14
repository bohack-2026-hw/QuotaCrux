"""Runs only in a separate sandbox; the candidate never shares this process or its files."""
import json
import re
import sys


def normalize(text):
    text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)
    return text.replace('\r\r\n', '\n').replace('\r\n', '\n').strip()


payload = json.load(sys.stdin)
# Upstream run_tests.py calls evaluate(actual, expected), irrespective of parameter names.
namespace = dict(globals())
exec(compile(payload['checker'], 'checker.py', 'exec'), namespace)
verdicts = [namespace['evaluate'](normalize(actual), normalize(expected)) for actual, expected in payload['pairs']]
if not all(type(v) is bool for v in verdicts):
    raise TypeError('evaluator must return bool')
print(json.dumps(verdicts))
