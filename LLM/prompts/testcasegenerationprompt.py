from LLM.prompts.prompt import Prompt


class TestCaseGenerationPrompt(Prompt):
    def build_prompt(self) -> str:
        # TODO: to replace after the prompt experimenting results
        return "Hi, this is placeholder prompt message"
