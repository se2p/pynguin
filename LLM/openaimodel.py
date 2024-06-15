import os
import re
import time
import pickle

import openai
import pynguin.configuration as config


def extract_python_code_from_llm_output(llm_output: str) -> str:
    """
    Extracts Python code blocks from the LLM output.

    Args:
    llm_output (str): The output from the LLM containing Python code.

    Returns:
    str: The extracted Python code.
    """
    code_blocks = re.findall(r"```python([\s\S]+?)```", llm_output)
    return "\n".join(code_blocks) if code_blocks else llm_output


def get_module_path():
    return os.path.join(config.configuration.project_path, config.configuration.module_name + ".py")


def get_module_source_code():
    full_path = get_module_path()
    try:
        with open(full_path, 'r') as file:
            return file.read()
    except FileNotFoundError:
        return None


class OpenAIModel:
    CACHE_FILE = "llm_output_cache.pkl"

    def __init__(self):
        self._model_name = config.LLMConfiguration.model_name
        self._max_query_len = config.LLMConfiguration.max_query_token_length
        self._temperature = config.LLMConfiguration.temperature
        self.llm_calls_counter = 0
        self.llm_calls_timer = 0

        openai.api_key = config.LLMConfiguration.api_key

        # Load cache if it exists
        if os.path.exists(self.CACHE_FILE):
            with open(self.CACHE_FILE, "rb") as f:
                self.cache = pickle.load(f)
        else:
            self.cache = {}

    def save_cache(self):
        with open(self.CACHE_FILE, "wb") as f:
            pickle.dump(self.cache, f)

    def query(self, prompt, max_tokens=1000):
        """
        Sends a query to the OpenAI API and returns the response.
        """
        start_time = time.time()
        self.llm_calls_counter += 1
        messages = [
            {
                "role": "user",
                "content": prompt.build_prompt()
            }
        ]
        response_text = None

        # Check cache first
        cache_key = str(messages)
        if cache_key in self.cache:
            response_text = self.cache[cache_key]
        else:
            try:
                response = openai.chat.completions.create(
                    model=self._model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=self._temperature
                )
                response_text = response.choices[0].message.content
                # Save response to cache
                self.cache[cache_key] = response_text
                self.save_cache()
            except openai.APIConnectionError as e:
                print("The server could not be reached")
            except openai.RateLimitError as e:
                print("A 429 status code was received; we should back off a bit.")
            except openai.APIStatusError as e:
                print("Another non-200-range status code was received")
                print(e.status_code)
                print(e.response)
            finally:
                self.llm_calls_timer += time.time() - start_time

        if response_text is None:
            return print("Response empty!")
        return response_text
