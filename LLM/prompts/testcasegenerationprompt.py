from LLM.prompts.prompt import Prompt


class TestCaseGenerationPrompt(Prompt):
    def build_prompt(self) -> str:

        test_case_example = """
        def test_method_x():
            str0 = 'x'
            str1 = 'z'
            class_var = Example()
            class_var.method_x(user0, str2)
        """

        return (
            f"Write comprehensive unit tests to cover methods in the module located at the path `{self.module_path}\n"
            "Guidelines:\n"
            "- Create one test case for each method in the module.\n"
            "- Cover standard inputs, edge cases, and error handling.\n"
            "- Avoid assertions in these tests, focus mainly on the coverage.\n\n"
            f"Example Test Case:\n{test_case_example}\n"
            f"Module code:\n{self.module_code}"
        )
