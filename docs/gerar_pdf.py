"""gerar_pdf.py — Utilitário genérico Markdown → PDF.

Uso:
    python gerar_pdf.py <arquivo.md> [arquivo.pdf]

Exemplo:
    python gerar_pdf.py CHANGELOG.md CHANGELOG.pdf
"""

import os
import sys

try:
    import markdown
    from weasyprint import HTML
except ImportError as e:
    print(f"❌ Dependências faltando: {e}")
    print("Instale com: pip install markdown weasyprint")
    sys.exit(1)


def md_to_pdf(md_path: str, pdf_path: str) -> str:
    """Converte Markdown para PDF e retorna o path do PDF gerado."""
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = markdown.markdown(
        md_content, extensions=["tables", "fenced_code", "toc"]
    )

    css = """
    @page {
        size: A4;
        margin: 2.5cm 2cm;
    }
    body {
        font-family: 'DejaVu Sans', sans-serif;
        font-size: 10pt;
        line-height: 1.5;
        color: #222;
        text-align: justify;
    }
    h1 {
        font-size: 18pt;
        color: #1a3c34;
        text-align: center;
        margin-bottom: 0.3cm;
        page-break-before: avoid;
    }
    h2 {
        font-size: 13pt;
        color: #2d6a4f;
        border-bottom: 2px solid #2d6a4f;
        padding-bottom: 3px;
        margin-top: 0.8cm;
        page-break-after: avoid;
    }
    h3 {
        font-size: 11pt;
        color: #40916c;
        margin-top: 0.5cm;
        page-break-after: avoid;
    }
    h4 {
        font-size: 10pt;
        color: #555;
        margin-top: 0.3cm;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 0.3cm 0;
        font-size: 9pt;
    }
    th {
        background-color: #2d6a4f;
        color: white;
        padding: 5px 7px;
        text-align: left;
    }
    td {
        padding: 3px 7px;
        border: 1px solid #ccc;
        vertical-align: top;
    }
    tr:nth-child(even) {
        background-color: #f0f7f4;
    }
    code {
        background-color: #f4f4f4;
        padding: 1px 4px;
        border-radius: 2px;
        font-family: 'DejaVu Sans Mono', monospace;
        font-size: 9pt;
    }
    pre {
        background-color: #f4f4f4;
        padding: 6px 8px;
        border-radius: 3px;
        font-size: 8.5pt;
        overflow-x: auto;
    }
    hr {
        border: 0;
        border-top: 1px solid #ccc;
        margin: 0.5cm 0;
    }
    ul, ol {
        margin: 0.2cm 0;
        padding-left: 0.8cm;
    }
    li {
        margin: 0.1cm 0;
    }
    strong {
        color: #1a3c34;
    }
    """

    html_full = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<style>{css}</style>
</head>
<body>
{html_content}
</body>
</html>"""

    HTML(string=html_full).write_pdf(pdf_path)
    return pdf_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Modo padrão: gera CHANGELOG.pdf a partir do CHANGELOG.md
        here = os.path.dirname(os.path.abspath(__file__))
        md_path = os.path.join(here, "CHANGELOG.md")
        pdf_path = os.path.join(here, "CHANGELOG.pdf")
    elif len(sys.argv) == 2:
        md_path = sys.argv[1]
        pdf_path = os.path.splitext(md_path)[0] + ".pdf"
    else:
        md_path = sys.argv[1]
        pdf_path = sys.argv[2]

    if not os.path.exists(md_path):
        print(f"❌ Arquivo não encontrado: {md_path}")
        sys.exit(1)

    result = md_to_pdf(md_path, pdf_path)
    print(f"✅ PDF gerado: {result}")
    print(f"   Tamanho: {os.path.getsize(result):,} bytes")
