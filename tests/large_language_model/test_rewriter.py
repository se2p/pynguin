import pytest

from pynguin.large_language_model.parsing import rewriter


@pytest.mark.parametrize(
    "llm_output, expected_snippet",
    [
        (
            # Basic setUp + addition
            """
class TestFoo:
    def setUp(self):
        self.x = 1
        self.y = 2

    def test_add(self):
        result = self.x + self.y
        assert result == 3
""",
            [
                "def test_add():",
                "var_0 = 1",
                "var_1 = 2",
                "result = var_0 + var_1",
                "assert result == 3",
            ],
        ),
        (
            # Method call with argument
            """
class TestCall:
    def setUp(self):
        self.data = [1, 2, 3]

    def test_len(self):
        length = len(self.data)
        assert length == 3
""",
            [
                "def test_len():",
                "var_1 = 1",
                "var_2 = 2",
                "var_3 = 3",
                "var_0 = [var_1, var_2, var_3]",
                "length = len(var_0)",
                "assert length == 3",
            ],
        ),
        (
            # isinstance assertion
            """
class TestIsInstance:
    def setUp(self):
        self.value = "hello"

    def test_type(self):
        assert isinstance(self.value, str)
""",
            [
                "def test_type():",
                "var_0 = 'hello'",
                "var_1 = isinstance(var_0, str)",
                "assert var_1",
            ],
        ),
        (
            # Nested attributes
            """
class SomeObject:
    def __init__(self):
        self.value = 5

class TestAttrAccess:
    def setUp(self):
        self.obj = SomeObject()

    def test_attr(self):
        v = self.obj.value
        assert v == 5
""",
            [
                "def test_attr():",
                "var_0 = SomeObject()",
                "v = var_0.value",
                "assert v == 5",
            ],
        ),
    ],
)
def test_rewrite_tests(llm_output, expected_snippet):
    result_dict = rewriter.rewrite_tests(llm_output)
    assert isinstance(result_dict, dict)
    assert any("test_" in fn_name for fn_name in result_dict)

    final_code = "\n".join(result_dict.values())
    for line in expected_snippet:
        assert line in final_code
