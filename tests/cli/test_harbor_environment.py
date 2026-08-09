# ABOUTME: Tests concrete Harbor environment selection at the CLI composition boundary.
# ABOUTME: Keeps Harbor-native backends separate from the explicit Morph binding.

from aec_bench.cli.harbor_environment import HARBOR_RUN_BACKENDS, resolve_harbor_environment_binding


def test_native_harbor_backend_needs_no_custom_binding() -> None:
    assert resolve_harbor_environment_binding("docker") is None


def test_morph_backend_resolves_the_provider_owned_binding() -> None:
    binding = resolve_harbor_environment_binding("morph")

    assert HARBOR_RUN_BACKENDS == ("modal", "e2b", "daytona", "docker", "morph")
    assert binding is not None
    assert binding.backend == "morph"
    assert binding.import_path == "aec_bench.providers.morph_harbor:MorphHarborEnvironment"
    assert binding.kwargs == {"compute_backend": "morph"}
