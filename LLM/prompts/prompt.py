from abc import abstractmethod


class Prompt:
    def __init__(self, module_code, module_path):
        self.module_code = module_code
        self.module_path = module_path

    @abstractmethod
    def build_prompt(self) -> str:
        pass
