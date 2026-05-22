import subprocess
import os
import shutil

SKILLS_DIR = os.path.expanduser("~/.agents/skills")

SKILLS = [
    ("https://github.com/gustavobraga-byte/Skill-IBGE.git", "ibge-br"),
    ("https://github.com/gustavobraga-byte/Skill-DataSus.git", "opendatasus"),
    ("https://github.com/K-Dense-AI/scientific-agent-skills.git", "scientific"),
    ("https://github.com/gustavobraga-byte/PesquisAI.git", "pesquisai"),
]


def run(cmd, check=True, **kw):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if check and result.returncode != 0:
        print(f"⚠️  Aviso: comando falhou: {cmd}\n{result.stderr}")
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
        print(f"❌ Falha ao clonar {repo_url}: {result.stderr.strip()}")
        return False
    print(f"✅ {dest_name} clonado.")
    return True


def install_skills():
    os.makedirs(SKILLS_DIR, exist_ok=True)
    
    for repo, name in SKILLS:
        clone_skill(repo, name)
    
    print("\n📋 Copiando skills para o diretório do agente...")
    
    mappings = [
        ("/tmp/skill_ibge-br", "ibge-br"),
        ("/tmp/skill_opendatasus", "opendatasus"),
        ("/tmp/skill_scientific/scientific-skills", "scientific"),
    ]
    
    for src, dest_name in mappings:
        dest = os.path.join(SKILLS_DIR, dest_name)
        if os.path.exists(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"✅ {dest_name} instalado.")
    
    print("\n🎉 Todas as skills instaladas com sucesso!")


if __name__ == "__main__":
    install_skills()
