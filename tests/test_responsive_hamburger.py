"""Regressão: com o menu hamburger visível, NENHUM ícone SVG aparece na topbar.

Bug real (29/09/2026): a regra `.tb-icon { display: none }` existia apenas nas
cópias de projeto (ufvai-github/, UFVAI-v0.6.9/) e NÃO no arquivo de produção
da raiz — por isso o usuário não via a mudança. Além disso a regra antiga tinha
especificidade (0,1,0), igual à da regra base `.tb-icon{display:inline-flex}`;
qualquer regra posterior com a mesma especificidade a vencia por cascata.

Este teste não faz grep no fonte: ele gera o HTML real, extrai os <style>,
parseia o CSS com tinycss2 e resolve a cascata (especificidade + !important +
ordem + style inline) para uma largura simulada. Assim pega tanto "regra
faltando" quanto "regra presente mas inefetiva".

Cobre os 7 arquivos vivos por padrão (raiz + 2 projetos x 2 módulos).
Override: UFVAI_RESPONSIVE_FILES="a.py,b.py"
"""

import importlib.util
import os
import re
import warnings

import pytest
import tinycss2
from bs4 import BeautifulSoup

# ── Arquivos vivos que precisam obedecer ao contrato ────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIVE_FILES = [
    os.path.join(_ROOT, "launch_app_responsive_v041.py"),
    os.path.join(_ROOT, "launch_app_responsive.py"),
    os.path.join(_ROOT, "launch_app_responsive_versaoteste_CORRIGIDO.py"),
    os.path.join(_ROOT, "ufvai-github", "pesquisai", "launch_app_responsive_v041.py"),
    os.path.join(_ROOT, "ufvai-github", "pesquisai", "launch_app_responsive.py"),
    os.path.join(_ROOT, "UFVAI-v0.6.9", "pesquisai", "launch_app_responsive_v041.py"),
    os.path.join(_ROOT, "UFVAI-v0.6.9", "pesquisai", "launch_app_responsive.py"),
]
_env = os.environ.get("UFVAI_RESPONSIVE_FILES")
if _env:
    LIVE_FILES = [os.path.abspath(p) for p in _env.split(",") if p.strip()]

MOBILE_WIDTHS = [320, 375, 414, 479, 600, 767]
DESKTOP_WIDTHS = [768, 900, 1024, 1440]


# ── Mini-parser de CSS ──────────────────────────────────────────────────────

def _walk(nodes, media, out):
    for node in nodes:
        if node.type == "at-rule" and node.lower_at_keyword == "media":
            cond = tinycss2.serialize(node.prelude).strip()
            _walk(tinycss2.parse_rule_list(node.content or []), cond, out)
        elif node.type == "qualified-rule":
            sel = tinycss2.serialize(node.prelude).strip()
            decls = tinycss2.parse_blocks_contents(node.content or [])
            out.append((media, sel, decls))


def parse_rules(css_text):
    out = []
    _walk(tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True),
          None, out)
    return out


def media_applies(cond, width):
    if not cond:
        return True
    m = re.search(r"max-width\s*:\s*(\d+)px", cond)
    if m and width > int(m.group(1)):
        return False
    m = re.search(r"min-width\s*:\s*(\d+)px", cond)
    if m and width < int(m.group(1)):
        return False
    return True


def _compound_matches(compound, el):
    tag, classes, eid = el
    for part in re.findall(r"#[\w-]+|\.[\w-]+|[a-zA-Z][\w-]*", compound):
        if part.startswith("#"):
            if eid != part[1:]:
                return False
        elif part.startswith("."):
            if part[1:] not in classes:
                return False
        else:
            if tag != part:
                return False
    return True


def selector_matches(selector, path):
    """path: lista de ancestrais -> elemento, do mais externo para o elemento."""
    parts = [p.strip() for p in re.split(r"\s+", selector) if p.strip()]
    if not parts:
        return False
    if not _compound_matches(parts[-1], path[-1]):
        return False
    i, j = len(parts) - 2, len(path) - 2
    while i >= 0 and j >= 0:
        if _compound_matches(parts[i], path[j]):
            i -= 1
        j -= 1
    return i < 0


def specificity(selector):
    return (
        len(re.findall(r"#[\w-]+", selector)),
        len(re.findall(r"\.[\w-]+", selector)),
        len(re.findall(r"(?:^|[\s>])[a-zA-Z][\w-]*", selector)),
    )


UNSUPPORTED = re.compile(r"[>+~:\[\(]")


# ── Resolvedor de cascata ───────────────────────────────────────────────────
# prioridade: !important de autor (3) > inline normal (2) > autor normal (1)

def _inline_candidates(prop, node_chain):
    out = []
    for i, node in enumerate(node_chain):
        st = node.get("style") if hasattr(node, "get") else None
        if not st:
            continue
        for d in tinycss2.parse_blocks_contents(st):
            if d.type == "declaration" and d.lower_name == prop:
                pr = 4 if d.important else 2
                out.append((pr, (0, 0, 0), i, tinycss2.serialize(d.value).strip()))
    return out


def computed(rules, prop, path, width, node_chain=None):
    """Resolve `prop` para o elemento `path` na largura `width` (cascata real)."""
    cands = list(_inline_candidates(prop, node_chain or []))
    for order, (media, sel, decls) in enumerate(rules):
        if not media_applies(media, width):
            continue
        for one in sel.split(","):
            one = one.strip()
            if not one or UNSUPPORTED.search(one):
                continue
            if not selector_matches(one, path):
                continue
            for d in decls:
                if d.type != "declaration" or d.lower_name != prop:
                    continue
                pr = 3 if d.important else 1
                cands.append((pr, specificity(one), order,
                              tinycss2.serialize(d.value).strip()))
    if not cands:
        return None
    return max(cands, key=lambda c: (c[0], c[1], c[2]))[3]


# ── Helpers de DOM ──────────────────────────────────────────────────────────

def _load(path):
    # Os arquivos legados da raiz embutem JS em string Python e disparam
    # SyntaxWarning no import (ex.: f.replace(/\/$/, "")) — é preexistente e
    # não afeta o HTML servido; aqui só polui o teste.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        spec = importlib.util.spec_from_file_location(
            "ufvai_resp_ut_%d" % abs(hash(path)), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod


def _html_and_rules(path):
    mod = _load(path)
    html = mod.create_wrapper_html("http://localhost:8000", "http://drive.local/x")
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))
    return html, parse_rules(css)


def _ancestors(node):
    out, cur = [], node.parent
    while cur is not None and cur.name:
        out.append(cur)
        cur = cur.parent
    return list(reversed(out))


def _el(node):
    return (node.name, set(node.get("class", [])), node.get("id"))


def _ancestor_path(node):
    """Caminho (ancestrais -> elemento) no formato esperado por selector_matches."""
    return [_el(a) for a in _ancestors(node)] + [_el(node)]


def oculta_em(rules, node, width, stop_at=None):
    """Um <svg> fica invisível se ELE ou qualquer ancestral tiver display:none
    (é assim que display:none funciona na prática)."""
    chain = _ancestors(node) + [node]
    if stop_at is not None:
        cut = chain.index(stop_at) if stop_at in chain else len(chain)
        chain = chain[cut:]
    for i, nd in enumerate(chain):
        d = computed(rules, "display", _ancestor_path(nd), width, node_chain=chain[i:])
        if d == "none":
            return nd
    return None


def oculta_em(rules, node, width, stop_at=None):
    """Um <svg> fica invisível se ELE ou qualquer ancestral tiver display:none
    (é assim que display:none funciona na prática)."""
    chain = _ancestors(node) + [node]
    if stop_at is not None:
        cut = chain.index(stop_at) if stop_at in chain else len(chain)
        chain = chain[cut:]
    for i, nd in enumerate(chain):
        d = computed(rules, "display", _ancestor_path(nd), width, node_chain=chain[i:])
        if d == "none":
            return nd
    return None

TOPBAR_ICON = [("div", {"topbar"}, "topbar"), ("button", {"tb-icon"}, None)]
HAMBURGER = [("div", {"topbar"}, "topbar"), ("button", {"hamburger"}, None)]
LANG_BTN = [("div", {"topbar"}, "topbar"), ("button", {"lang-btn"}, "lang-btn")]
# Alinhamento (bug 29/09/2026): .sep { flex:1 } absorvia todo o espaco livre do
# #topbar e, como flex-grow e resolvido antes das margens auto, o
# margin-left:auto do .tb-icons valia 0 -> o hamburger encostava no logo.
TOPBAR_SEP = [("div", {"topbar"}, "topbar"), ("div", {"sep"}, None)]
TOPBAR_ICONS = [("div", {"topbar"}, "topbar"), ("div", {"tb-icons"}, None)]
DRAWER_BTN = [("div", {"mobile-menu"}, "mobile-menu"), ("button", {"tb-btn"}, None)]
DRAWER_SVG = DRAWER_BTN + [("svg", set(), None)]


# ── Testes ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", LIVE_FILES,
                         ids=[os.path.relpath(p, _ROOT) for p in LIVE_FILES])
class TestHamburgerSemIconeSVG:
    def test_arquivo_existe(self, path):
        assert os.path.isfile(path), f"arquivo vivo ausente: {path}"

    def test_gera_html_com_hamburger(self, path):
        html, _ = _html_and_rules(path)
        soup = BeautifulSoup(html, "html.parser")
        assert soup.select_one("#topbar button.hamburger") is not None
        assert soup.select_one("#mobile-menu") is not None

    @pytest.mark.parametrize("w", MOBILE_WIDTHS)
    def test_mobile_tb_icon_display_none(self, path, w):
        _, rules = _html_and_rules(path)
        assert computed(rules, "display", TOPBAR_ICON, w) == "none", (
            f"a <= {w}px o .tb-icon deveria estar display:none (hamburger visivel)")

    @pytest.mark.parametrize("w", MOBILE_WIDTHS)
    def test_mobile_hamburger_e_idioma_visiveis(self, path, w):
        _, rules = _html_and_rules(path)
        assert computed(rules, "display", HAMBURGER, w) == "inline-flex"
        assert computed(rules, "display", LANG_BTN, w) not in (None, "none")

    @pytest.mark.parametrize("w", DESKTOP_WIDTHS)
    def test_desktop_tb_icon_visivel(self, path, w):
        _, rules = _html_and_rules(path)
        d = computed(rules, "display", TOPBAR_ICON, w)
        assert d not in (None, "none"), f"a >= {w}px os icones devem voltar"

    @pytest.mark.parametrize("w", MOBILE_WIDTHS)
    def test_drawer_sem_svg_e_com_botoes_visiveis(self, path, w):
        _, rules = _html_and_rules(path)
        assert computed(rules, "display", DRAWER_BTN, w) == "inline-flex"
        assert computed(rules, "display", DRAWER_SVG, w) == "none"

    def test_todo_svg_da_topbar_some_no_mobile(self, path):
        """Estrutural + cascata: nenhum <svg> da topbar fica visível a 375px,
        exceto o próprio SVG do hamburger."""
        html, rules = _html_and_rules(path)
        soup = BeautifulSoup(html, "html.parser")
        topbar = soup.select_one("#topbar")
        svgs = topbar.select("svg")
        assert svgs, "a topbar deveria conter os botoes-icone"
        for svg in svgs:
            if any("hamburger" in (a.get("class") or []) for a in _ancestors(svg)):
                continue  # o proprio hamburguer precisa existir
            host = svg.find_parent(["button", "a"])
            assert oculta_em(rules, svg, 375, stop_at=topbar) is not None, (
                f"<svg> dentro de <{host}> ficaria VISIVEL a 375px "
                "- apareceria junto com o hamburger")

    def test_todo_svg_do_drawer_some_no_mobile(self, path):
        html, rules = _html_and_rules(path)
        soup = BeautifulSoup(html, "html.parser")
        drawer = soup.select_one("#mobile-menu")
        svgs = drawer.select("svg")
        assert svgs, "o drawer deveria conter os botoes migrados da topbar"
        for svg in svgs:
            host = svg.find_parent(["button", "a"])
            assert oculta_em(rules, svg, 375, stop_at=drawer) is not None, (
                f"<svg> dentro de <{host}> ficaria VISIVEL dentro do menu a 375px")

    @pytest.mark.parametrize("w", MOBILE_WIDTHS)
    def test_mobile_hamburger_alinhado_a_direita(self, path, w):
        """O .sep nao pode competir com o margin-left:auto do .tb-icons."""
        _, rules = _html_and_rules(path)
        assert computed(rules, "display", TOPBAR_SEP, w) == "none", (
            f"a <= {w}px o .sep precisa sumir: flex:1 vence margin-left:auto "
            "na resolucao do flexbox e empurra o .tb-icons para a ESQUERDA")
        assert computed(rules, "margin-left", TOPBAR_ICONS, w) == "auto", (
            f"a <= {w}px o .tb-icons precisa de margin-left:auto para encostar "
            "o hamburger na borda direita do #topbar")

    @pytest.mark.parametrize("w", DESKTOP_WIDTHS)
    def test_desktop_mantem_o_spacer_do_topbar(self, path, w):
        """Regressao do inverso: no desktop o .sep volta a separar os botoes."""
        _, rules = _html_and_rules(path)
        assert computed(rules, "display", TOPBAR_SEP, w) != "none", (
            f"a >= {w}px o .sep precisa continuar como spacer (flex:1) do topbar")
        assert computed(rules, "margin-left", TOPBAR_ICONS, w) == "6px", (
            f"a >= {w}px o .tb-icons volta a encostar no logo (sem auto)")
