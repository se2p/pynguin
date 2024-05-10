from abc import abstractmethod


class Prompt:
    def __init__(self):
        self.module_code = None
        self.module_path = None

    def set_module_code(self, module_code: str):
        self.module_code = module_code

    def get_module_code(self):
        return self.module_code

    def set_module_path(self, module_path: str):
        self.module_path = module_path

    def get_module_path(self):
        return self.module_path

    @abstractmethod
    def build_prompt(self) -> str:
        pass
