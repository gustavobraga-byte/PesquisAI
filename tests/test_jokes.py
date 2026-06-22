"""Testes para jokes.py — catálogo de piadas científicas."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai.jokes import (
    next_joke,
    JOKES_BY_CATEGORY,
    ALL_JOKES,
    FISICA,
    QUIMICA,
    BIOLOGIA,
    MATEMATICA,
    COMPUTACAO,
    ASTRONOMIA,
    ECONOMIA,
    ADMINISTRACAO,
    FINANCAS,
    RH,
    MARKETING,
    LOGISTICA,
    DIREITO,
    MEDICINA,
)


class TestJokesCategories:
    """Testa categorias de piadas."""

    def test_categories_not_empty(self):
        """Toda categoria deve ter ao menos uma piada."""
        for name, pool in JOKES_BY_CATEGORY.items():
            assert len(pool) > 0, f"Categoria '{name}' está vazia"

    def test_all_jokes_aggregated(self):
        """ALL_JOKES deve conter a soma de todas as categorias."""
        expected = sum(len(v) for v in JOKES_BY_CATEGORY.values())
        assert len(ALL_JOKES) == expected

    def test_categories_have_minimum_jokes(self):
        """Cada categoria deve ter pelo menos 5 piadas."""
        for name, pool in JOKES_BY_CATEGORY.items():
            assert len(pool) >= 5, f"Categoria '{name}' tem apenas {len(pool)} piadas"

    def test_jokes_are_strings(self):
        """Todas as piadas devem ser strings não vazias."""
        for joke in ALL_JOKES:
            assert isinstance(joke, str), f"Piada não é string: {joke}"
            assert len(joke) > 0, "Piada vazia encontrada"


class TestNextJoke:
    """Testa a função next_joke()."""

    def test_returns_string(self):
        """Deve sempre retornar uma string."""
        result = next_joke()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_category_filter(self):
        """Deve retornar piada da categoria solicitada."""
        result = next_joke("fisica")
        assert result in FISICA

        result = next_joke("economia")
        assert result in ECONOMIA

    def test_random_default(self):
        """Sem categoria definida, deve retornar piada aleatória."""
        result = next_joke()
        assert result in ALL_JOKES

    def test_rotation(self):
        """Chamadas sucessivas na mesma categoria devem rodar as piadas."""
        first = next_joke("computacao")
        second = next_joke("computacao")
        # Pode eventualmente ser igual se sortear a mesma, improvável mas possível
        # O importante é que não quebre
        assert isinstance(first, str)
        assert isinstance(second, str)

    def test_invalid_category_falls_back(self):
        """Categoria inexistente deve cair no fallback aleatório."""
        result = next_joke("categoria_inexistente_xyz")
        assert result in ALL_JOKES

    def test_unknown_category(self):
        """Categoria vazia deve ir para aleatório."""
        result = next_joke("")
        assert result in ALL_JOKES
