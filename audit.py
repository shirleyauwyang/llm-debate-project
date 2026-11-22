"""Audit saved completions before voting."""
import re
from decimal import Decimal, InvalidOperation

FINAL = re.compile(r"^[ \t]*(?:\*\*|`)*[ \t]*FINAL[_ ]ANSWER[ \t]*:[ \t]*(.*)$", re.I | re.M)
NUMBER = re.compile(r"[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")

def audit(response, question):
    if response["finish"] != "stop":
        return None, "finish_not_stop"
    matches = FINAL.findall(response["text"])
    if len(matches) != 1:
        return None, "multiple_final_answers" if matches else "missing_final_answer"
    value = matches[0].strip().strip("*` ").strip()
    if question["dataset"] == "mmlu":
        value = value.upper()
        if re.fullmatch("[A-J]", value):
            if ord(value) - ord("A") < len(question["options"]):
                return value, None
            return None, "unavailable_option"
    elif NUMBER.fullmatch(value):
        try:
            value = Decimal(value.replace(",", ""))
            if value.is_finite():
                return str(value.normalize()), None
        except InvalidOperation:
            pass
    return None, "invalid_answer_format"

def status(answer, truth):
    if answer is None:
        return "invalid"
    return "correct" if answer == truth else "wrong"
