import unittest

from src.agents.model_registry import ModelRegistry, ModelUnavailableError


class ModelRegistryTests(unittest.TestCase):
    def test_loader_runs_once_and_version_is_reported(self):
        calls = []
        registry = ModelRegistry()
        registry.register(
            "similarity",
            "minilm-local-v1",
            lambda: calls.append(1) or object(),
        )

        first = registry.get("similarity")
        second = registry.get("similarity")

        self.assertIs(first, second)
        self.assertEqual(calls, [1])
        self.assertEqual(registry.versions(), {"similarity": "minilm-local-v1"})

    def test_optional_failure_is_isolated_as_warning(self):
        registry = ModelRegistry()
        registry.register(
            "forecaster",
            "unavailable",
            lambda: (_ for _ in ()).throw(RuntimeError("artifact missing")),
            optional=True,
        )

        model, warning = registry.try_get("forecaster")

        self.assertIsNone(model)
        self.assertEqual(warning.code, "model_unavailable")
        self.assertEqual(warning.capability, "forecaster")

    def test_required_failure_raises_model_unavailable_error(self):
        registry = ModelRegistry()
        registry.register("required", "v1", lambda: 1 / 0, optional=False)
        with self.assertRaises(ModelUnavailableError):
            registry.get("required")


if __name__ == "__main__":
    unittest.main()
