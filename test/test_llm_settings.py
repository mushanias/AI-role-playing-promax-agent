"""LLM 内置与自定义预设测试。"""

import unittest

from app.exceptions import InvalidLLMConfigurationError
from app.llm import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    MODEL_SETTINGS,
    build_llm_model,
)


class LLMSettingsTests(unittest.TestCase):
    def test_default_model_is_minimax_m3(self) -> None:
        self.assertEqual(DEFAULT_LLM_PROVIDER, "minimax")
        self.assertEqual(DEFAULT_LLM_MODEL, "MiniMax-M3")

    def test_catalog_contains_requested_providers(self) -> None:
        self.assertEqual(
            set(MODEL_SETTINGS),
            {"deepseek", "openai", "anthropic", "xai", "glm", "minimax"},
        )

    def test_build_builtin_model_uses_preset_details(self) -> None:
        setting = MODEL_SETTINGS["glm"]
        model = build_llm_model(
            api_key="secret",
            provider="glm",
        )

        self.assertEqual(model["sdk"], "openai_chat")
        self.assertEqual(model["client_params"]["api_key"], "secret")
        self.assertEqual(
            model["request_params"]["model"],
            setting["request_params"]["model"],
        )

    def test_build_builtin_model_rejects_unknown_model(self) -> None:
        with self.assertRaises(InvalidLLMConfigurationError):
            build_llm_model(
                api_key="secret",
                provider="glm",
                model="unknown",
            )

    def test_build_custom_model(self) -> None:
        model = build_llm_model(
            api_key="secret",
            custom_setting={
                "name": "自定义",
                "sdk": "openai_chat",
                "client_params": {"base_url": "https://example.com/v1"},
                "request_params": {
                    "model": "custom-model",
                    "max_tokens": 4096,
                },
            },
        )

        self.assertEqual(model["provider"], "自定义")
        self.assertEqual(
            model["client_params"],
            {"base_url": "https://example.com/v1", "api_key": "secret"},
        )


if __name__ == "__main__":
    unittest.main()
