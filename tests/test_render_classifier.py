"""Error classifier, using tracebacks shaped like real Manim output."""
import pytest

from c2a.render import classify_error


@pytest.mark.parametrize("output, expected", [
    ("NameError: name 'ShowCreation' is not defined", "hallucinated_api"),
    ("AttributeError: 'Axes' object has no attribute 'get_graph'", "hallucinated_api"),
    ("ModuleNotFoundError: No module named 'manimlib'", "hallucinated_api"),
    ("ImportError: cannot import name 'TextMobject' from 'manim'", "hallucinated_api"),
    # Mobject.__getattr__ turns unknown get_* calls into TypeErrors
    ("File mobject.py in getter\nTypeError: Mobject.__getattr__.<locals>.getter() takes 1 positional "
     "argument but 2 were given", "hallucinated_api"),
    ("TypeError: Mobject.__init__() got an unexpected keyword argument 'bogus_kw'", "bad_signature"),
    ("! Undefined control sequence.\nValueError: latex error converting to dvi. See log output above",
     "latex"),
    ("SyntaxError: expected ':'", "syntax"),
    ("IndentationError: unexpected indent", "syntax"),
    ("ZeroDivisionError: division by zero", "other"),
    ("something went wrong with no exception line", "other"),
])
def test_classify(output, expected):
    assert classify_error(output)[0] == expected


def test_message_is_last_exception_line():
    out = "Traceback...\nKeyError: 'x'\nduring handling...\nNameError: name 'Foo' is not defined"
    assert classify_error(out)[1] == "NameError: name 'Foo' is not defined"


def test_rich_box_chars_are_stripped():
    out = "│ NameError: name 'ShowCreation' is not defined │"
    assert classify_error(out) == ("hallucinated_api", "NameError: name 'ShowCreation' is not defined")


def test_bare_exception_without_message():
    out = ("│ manim/animation/transform_matching_parts.py:300 in get_mobject_key │\n"
           "│ ❱ 300 │ assert isinstance(mobject, MathTexPart) │\n"
           "AssertionError\n")
    etype, msg = classify_error(out)
    assert etype == "other"
    assert msg.startswith("AssertionError") and "get_mobject_key" in msg
