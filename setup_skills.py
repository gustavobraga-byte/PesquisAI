import subprocess
import os
import shutil

SKILLS_DIR = os.path.expanduser("~/.agents/skills")

SKILLS = [
    ("https://github.com/gustavobraga-byte/Skill-IBGE.git", "ibge-br"),
    ("https://github.com/gustavobraga-byte/Skill-DataSus.git", "opendatasus"),
    ("https://github.com/K-Dense-AI/scientific-agent-skills.git", "scientific"),
    ("https://github.com/gustavobraga-byte/PesquisAI.git", "pesquisai"),
    ("https://github.com/gustavobraga-byte/UFV-ABNT.git", "ufv-abnt"),
]

JOKES_SKILLS = [
    "🧬 Se a evolução dependesse dessa velocidade, ainda seríamos amebas.",
    "💻 Mais lento que bubble sort em 1 milhão de elementos.",
    "🧬 Mais lento que a duplicação do DNA em uma lesma.",
    "💻 Deadlock: você e o download estão esperando um pelo outro.",
    "🧬 Seu progresso está em metáfase: parado no meio.",
    "💻 Loop infinito: while not terminou: espere()",
    "🧬 A paciência é o gene dominante nesse momento.",
    "💻 Complexidade O(n²), onde n = sua paciência.",
    "🧬 Célula em G0: fase de espera prolongada.",
    "💻 Pilha de chamada: você está no fundo da pilha.",
    "📚 Instalando ABNT: a única regra que não muda é que ela sempre muda.",
    "📖 Formatação ABNT: transformando sua tese em dor de cabeça desde 1940.",
    "📝 Citações ABNT: porque referenciar um autor deveria ser mais complicado que a própria pesquisa.",
]

_joke_index = 0

def next_joke():
    global _joke_index
    if _joke_index < len(JOKES_SKILLS):
        joke = JOKES_SKILLS[_joke_index]
        _joke_index += 1
        return joke
    return JOKES_SKILLS[-1]


def run(cmd, check=True, **kw):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if check and result.returncode != 0:
        print(f"⚠️  Aviso: comando falhou: {cmd}")
    return result


def clone_skill(repo_url, dest_name):
    tmp = f"/tmp/skill_{dest_name}"
    if os.path.exists(tmp):
        shutil.rmtree(tmp)
    
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, tmp],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ Falha ao clonar {repo_url}")
        return False
    print(f"✅ {dest_name} clonado.")
    return True


def install_skills():
    print(f"\n{next_joke()}")
    print("🔧 Instalando skills...")
    os.makedirs(SKILLS_DIR, exist_ok=True)
    
    for repo, name in SKILLS:
        clone_skill(repo, name)
    
    print(f"\n{next_joke()}")
    print("📋 Copiando skills para o diretório do agente...")
    
    mappings = [
        ("/tmp/skill_ibge-br", "ibge-br"),
        ("/tmp/skill_opendatasus", "opendatasus"),
        ("/tmp/skill_scientific/scientific-skills", "scientific"),
        ("/tmp/skill_ufv-abnt", "ufv-abnt"),
    ]
    
    for src, dest_name in mappings:
        dest = os.path.join(SKILLS_DIR, dest_name)
        if os.path.exists(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"✅ {dest_name} instalado.")
    
    print(f"\n{next_joke()}")
    print("\n🎉 Todas as skills instaladas com sucesso!")


if __name__ == "__main__":
    install_skills()
