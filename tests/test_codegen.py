from c2a.codegen import enforce_class_name, extract_code


def test_extract_fenced_python():
    text = "Here you go:\n```python\nfrom manim import *\nx = 1\n```\nEnjoy!"
    assert extract_code(text) == "from manim import *\nx = 1\n"


def test_extract_picks_longest_block():
    text = "```bash\npip install manim\n```\n```python\nfrom manim import *\nclass A(Scene):\n    pass\n```"
    assert "class A(Scene)" in extract_code(text)


def test_extract_no_fence_returns_text():
    assert extract_code("from manim import *") == "from manim import *\n"


def test_rename_scene_class():
    code = "class PythagorasScene(Scene):\n    def construct(self):\n        super(PythagorasScene, self)\n"
    new, old = enforce_class_name(code, "Scene2")
    assert old == "PythagorasScene"
    assert "class Scene2(Scene):" in new and "PythagorasScene" not in new


def test_rename_handles_moving_camera_scene():
    new, old = enforce_class_name("class Foo(MovingCameraScene):\n    pass\n", "Scene1")
    assert old == "Foo" and new.startswith("class Scene1(MovingCameraScene):")


def test_already_named_is_untouched():
    code = "class Scene3(Scene):\n    pass\n"
    assert enforce_class_name(code, "Scene3") == (code, None)
