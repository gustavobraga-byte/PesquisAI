"""pesquisai/free_models.py — v0.7.9: modelos gratuitos e padrão do motor.

Funções puras (sem rede e sem escrever em disco por si só), para que o
seletor de gratuitos e o modelo padrão sejam testáveis.

Regras:
- OpenRouter: só modelos com sufixo ``:free`` e o roteador ``openrouter/free``.
- Google: modelos ``google/*`` (Gemini) com free tier no AI Studio.
- NVIDIA: modelos ``nvidia/*`` do catálogo NVIDIA (uso gratuito com chave NVIDIA;
  limites e termos são do provedor).
- OpenCode Go é PAGO e aparece só como link.

Responsabilidade: as chaves de API são do próprio usuário e não têm qualquer
vínculo com a plataforma UFVAI.
"""

from __future__ import annotations

from typing import Any, Iterable

FREE_PROVIDER_IDS: tuple[str, ...] = ("google", "nvidia", "openrouter")

KEY_LINKS: dict[str, str] = {
    "google": "https://aistudio.google.com/api-keys",
    "nvidia": "https://build.nvidia.com/",
    "openrouter": "https://openrouter.ai/keys",
    "opencode_go": "https://opencode.ai/go",
}

CHAVES_DOC_URL = (
    "https://github.com/gustavobraga-byte/PesquisAI/blob/main/docs/CHAVES_API.md"
)


def is_free_model(model_id: str) -> bool:
    """True se o identificador ``provedor/modelo`` é um modelo gratuito suportado."""
    mid = (model_id or "").strip()
    if mid.startswith("openrouter/"):
        rest = mid[len("openrouter/"):]
        return rest == "free" or rest.endswith(":free")
    if mid.startswith("nvidia/"):
        return len(mid) > len("nvidia/")
    if mid.startswith("google/"):
        # Gemini tem free tier no AI Studio; a cota é do provedor.
        return len(mid) > len("google/")
    return False


def provider_of(model_id: str) -> str:
    return (model_id or "").split("/", 1)[0]


def filter_free_models(lines: Iterable[str]) -> list[dict[str, str]]:
    """Filtra a saída de ``opencode models`` mantendo só os gratuitos suportados."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for raw in lines:
        mid = (raw or "").strip()
        if not mid or " " in mid or not is_free_model(mid) or mid in seen:
            continue
        seen.add(mid)
        out.append({"id": mid, "provider": provider_of(mid)})
    out.sort(key=lambda m: (FREE_PROVIDER_IDS.index(m["provider"]), m["id"]))
    return out


def merge_default_model(existing: dict[str, Any], model_id: str) -> dict[str, Any]:
    """Define ``model`` (padrão do motor) preservando o restante da configuração."""
    if not is_free_model(model_id):
        raise ValueError(f"modelo não é gratuito suportado: {model_id!r}")
    merged = dict(existing)
    merged["model"] = model_id
    return merged
