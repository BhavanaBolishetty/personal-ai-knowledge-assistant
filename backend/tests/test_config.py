from app.core.config import _resolve_embedding_config, settings


def test_gemini_provider_resolves_to_gemini_embedding_001_and_768(monkeypatch):
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("GEMINI_EMBEDDING_DIMENSION", raising=False)

    model_name, dimension = _resolve_embedding_config("gemini")

    assert model_name == "gemini-embedding-001"
    assert dimension == 768


def test_local_provider_resolves_to_minilm_and_384(monkeypatch):
    monkeypatch.delenv("LOCAL_EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("LOCAL_EMBEDDING_DIMENSION", raising=False)

    model_name, dimension = _resolve_embedding_config("local")

    assert model_name == "all-MiniLM-L6-v2"
    assert dimension == 384


def test_gemini_config_is_unaffected_by_stale_generic_env_vars(monkeypatch):
    # Reproduces the exact production bug: an old .env file with generic
    # EMBEDDING_MODEL_NAME/EMBEDDING_DIMENSION values (predating
    # EMBEDDING_PROVIDER existing at all) must NOT leak into the Gemini
    # provider's resolved config — those names aren't read for either
    # provider anymore, precisely so this can't happen.
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "384")
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("GEMINI_EMBEDDING_DIMENSION", raising=False)

    model_name, dimension = _resolve_embedding_config("gemini")

    assert model_name == "gemini-embedding-001"
    assert dimension == 768


def test_local_config_is_unaffected_by_gemini_specific_overrides(monkeypatch):
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL_NAME", "some-other-gemini-model")
    monkeypatch.setenv("GEMINI_EMBEDDING_DIMENSION", "1536")
    monkeypatch.delenv("LOCAL_EMBEDDING_MODEL_NAME", raising=False)
    monkeypatch.delenv("LOCAL_EMBEDDING_DIMENSION", raising=False)

    model_name, dimension = _resolve_embedding_config("local")

    assert model_name == "all-MiniLM-L6-v2"
    assert dimension == 384


def test_gemini_config_respects_its_own_explicit_overrides(monkeypatch):
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL_NAME", "gemini-embedding-002-preview")
    monkeypatch.setenv("GEMINI_EMBEDDING_DIMENSION", "1536")

    model_name, dimension = _resolve_embedding_config("gemini")

    assert model_name == "gemini-embedding-002-preview"
    assert dimension == 1536


def test_settings_singleton_reflects_local_provider_by_default():
    # This test environment doesn't set EMBEDDING_PROVIDER, so the
    # already-imported module-level `settings` singleton must resolve to
    # the local model/dimension — every other test in this suite assumes
    # settings.embedding_dimension == 384.
    assert settings.embedding_provider == "local"
    assert settings.embedding_model_name == "all-MiniLM-L6-v2"
    assert settings.embedding_dimension == 384
