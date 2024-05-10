import time

import openai

from src.pynguin import configuration


class OpenAIModel:

    def __init__(
         self,
         api_key: str = configuration.LLMConfiguration.api_key,
         model_name: str = configuration.LLMConfiguration.model_name,
         max_query_len: int = configuration.LLMConfiguration.max_query_token_length,
         temperature: float = configuration.LLMConfiguration.temperature
    ):
        self._model_name = model_name
        self._max_query_len = max_query_len
        self._temperature = temperature
        self.llm_calls_counter = 0
        self.llm_calls_timer = 0

        openai.api_key = api_key

    def query(self, prompt, max_tokens=100):
        """
        Sends a query to the OpenAI API and returns the response.
        """
        start_time = time.time()
        self.llm_calls_counter += 1
        try:
            response = openai.Completion.create(
                model=self._model_name,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=self._temperature
            )
            response_text = response.choices[0].text.strip()
        except Exception as e:
            print(f"An error occurred: {e}")
            response_text = None
        finally:
            self.llm_calls_timer += time.time() - start_time
        return response_text
