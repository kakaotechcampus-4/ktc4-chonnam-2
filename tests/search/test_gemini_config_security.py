import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.errors import (
    GeminiBaseUrlRejectionReason,
    UnsafeGeminiBaseUrlError,
)


def test_config_preserves_current_defaults_when_created() -> None:
    # Given: no environment overrides
    # When: the Gemini configuration is constructed
    config = GeminiSearchConfig()

    # Then: the current model, media, and tenant proxy defaults remain available
    assert config.model == "gemini-3.8-flash"
    assert config.media_resolution == "low"
    assert config.fine_media_resolution == "high"
    assert config.base_url == "https://mlapi.run/a90d8545-f100-4276-bf86-eb774596b91d/v1"


def test_config_preserves_model_media_and_base_url_from_dotenv() -> None:
    # Given: valid Gemini environment overrides
    environment = {
        "DAESINGO_GEMINI_MODEL": "gemini-2.5-flash",
        "DAESINGO_GEMINI_MEDIA_RESOLUTION": "medium",
        "DAESINGO_GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta",
    }

    # When: the configuration is loaded from the environment mapping
    config = GeminiSearchConfig.from_dotenv(environment)

    # Then: the configured values are preserved
    assert config.model == "gemini-2.5-flash"
    assert config.media_resolution == "medium"
    assert config.base_url == "https://generativelanguage.googleapis.com/v1beta"


@pytest.mark.parametrize(
    "base_url",
    (
        "https://mlapi.run/tenant/v1",
        "https://mlapi.run:443/tenant/v1",
        "https://generativelanguage.googleapis.com/v1beta/models",
    ),
)
def test_config_accepts_an_approved_https_host_with_a_path(base_url: str) -> None:
    # Given: an approved Gemini endpoint with a provider-specific path
    # When: the configuration is constructed
    config = GeminiSearchConfig(base_url=base_url)

    # Then: its exact base URL is preserved without normalization
    assert config.base_url == base_url


@pytest.mark.parametrize(
    ("base_url", "reason"),
    (
        ("http://mlapi.run/v1", GeminiBaseUrlRejectionReason.HTTPS_REQUIRED),
        ("mlapi.run/v1", GeminiBaseUrlRejectionReason.HTTPS_REQUIRED),
        ("/tenant/v1", GeminiBaseUrlRejectionReason.HTTPS_REQUIRED),
        ("https://user:secret@mlapi.run/v1", GeminiBaseUrlRejectionReason.USERINFO),
        ("https://mlapi.run/v1#fragment", GeminiBaseUrlRejectionReason.FRAGMENT),
        ("https://unknown.example/v1", GeminiBaseUrlRejectionReason.UNAPPROVED_HOST),
        ("https://proxy.local/v1", GeminiBaseUrlRejectionReason.UNAPPROVED_HOST),
        (
            "https://mlapi.run.evil.example/v1",
            GeminiBaseUrlRejectionReason.UNAPPROVED_HOST,
        ),
        ("https://mlapi.run:444/v1", GeminiBaseUrlRejectionReason.NON_DEFAULT_PORT),
        ("https://mlapi.run/v1?token=secret", GeminiBaseUrlRejectionReason.QUERY),
        ("https://mlapi.run:invalid/v1", GeminiBaseUrlRejectionReason.MALFORMED),
    ),
)
def test_config_rejects_unsafe_base_urls_at_construction(
    base_url: str, reason: GeminiBaseUrlRejectionReason
) -> None:
    # Given: a base URL outside the approved Gemini endpoint policy
    # When: the configuration is constructed
    with pytest.raises(UnsafeGeminiBaseUrlError) as caught:
        GeminiSearchConfig(base_url=base_url)

    # Then: construction cannot return an unsafe configuration
    assert caught.value.reason is reason
    assert str(caught.value) == f"unsafe Gemini base URL: {reason}"
    assert "secret" not in str(caught.value)
    assert "token" not in str(caught.value)


def test_config_rejects_an_unsafe_base_url_from_dotenv() -> None:
    # Given: an environment override pointing to a host-confusion endpoint
    environment = {"DAESINGO_GEMINI_BASE_URL": "https://mlapi.run.evil.example/v1"}

    # When: the configuration is loaded from the environment mapping
    with pytest.raises(UnsafeGeminiBaseUrlError) as caught:
        GeminiSearchConfig.from_dotenv(environment)

    # Then: the unsafe override cannot reach provider construction
    assert caught.value.reason is GeminiBaseUrlRejectionReason.UNAPPROVED_HOST
