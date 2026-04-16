import unittest
from unittest.mock import patch

from core.model_registry import OpenRouterModelRegistry


def make_model(
    model_id,
    name,
    input_modalities,
    output_modalities=("text",),
    prompt="0",
    completion="0",
    context_length=128000,
    supported_parameters=(),
):
    return {
        "id": model_id,
        "name": name,
        "context_length": context_length,
        "architecture": {
            "input_modalities": list(input_modalities),
            "output_modalities": list(output_modalities),
        },
        "pricing": {
            "prompt": prompt,
            "completion": completion,
        },
        "supported_parameters": list(supported_parameters),
    }


class TestOpenRouterModelRegistry(unittest.TestCase):
    def test_filters_out_text_only_models(self):
        models = [
            make_model("text/model", "Text Only", ("text",)),
            make_model("vision/model", "Vision Model", ("text", "image")),
        ]

        with patch.object(OpenRouterModelRegistry, "fetch_models", return_value=models):
            result = OpenRouterModelRegistry.get_models(free_only=True)

        self.assertEqual([model["id"] for model in result], ["vision/model"])

    def test_filters_out_specialized_models(self):
        models = [
            make_model("openrouter/free", "Free Models Router", ("text", "image")),
            make_model("meta-llama/llama-guard-4-12b:free", "Llama Guard", ("text", "image")),
            make_model("google/lyria-3-pro-preview", "Lyria 3 Pro", ("text", "image"), ("text", "audio")),
            make_model("google/gemma-3-27b-it:free", "Gemma 3 27B", ("text", "image")),
        ]

        with patch.object(OpenRouterModelRegistry, "fetch_models", return_value=models):
            result = OpenRouterModelRegistry.get_models(free_only=True)

        self.assertEqual([model["id"] for model in result], ["google/gemma-3-27b-it:free"])

    def test_models_are_ranked_by_live_metadata_without_fixed_recommendations(self):
        models = [
            make_model(
                "new/stronger-vl:free",
                "New Stronger VL",
                ("text", "image", "pdf", "video"),
                context_length=1000000,
                supported_parameters=("reasoning",),
            ),
            make_model(
                "google/gemma-4-26b-a4b-it:free",
                "Google: Gemma 4 26B A4B (free)",
                ("text", "image", "video"),
                context_length=262144,
                supported_parameters=("reasoning",),
            ),
            make_model(
                "google/gemma-4-31b-it:free",
                "Google: Gemma 4 31B (free)",
                ("text", "image", "video"),
                context_length=262144,
                supported_parameters=("reasoning",),
            ),
        ]

        with patch.object(OpenRouterModelRegistry, "fetch_models", return_value=models):
            options = OpenRouterModelRegistry.get_model_options(free_only=True)

        labels = list(options.keys())
        self.assertEqual(list(options.values())[0], "new/stronger-vl:free")
        self.assertTrue(labels[0].startswith("New Stronger VL"))
        self.assertNotIn("Recommended free", labels[0])
        self.assertIn("reasoning", labels[0])

    def test_paid_models_only_appear_with_full_access(self):
        models = [
            make_model("free/vision", "Free Vision", ("text", "image")),
            make_model("paid/vision", "Paid Vision", ("text", "image"), prompt="0.000001", completion="0.000002"),
        ]

        with patch.object(OpenRouterModelRegistry, "fetch_models", return_value=models):
            free_options = OpenRouterModelRegistry.get_model_options(free_only=True)
            full_options = OpenRouterModelRegistry.get_model_options(free_only=False)

        self.assertEqual(set(free_options.values()), {"free/vision"})
        self.assertEqual(set(full_options.values()), {"free/vision", "paid/vision"})
        paid_label = next(label for label, model_id in full_options.items() if model_id == "paid/vision")
        self.assertIn("~$1.00/M input", paid_label)


if __name__ == "__main__":
    unittest.main()
