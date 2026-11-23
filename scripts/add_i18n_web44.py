#!/usr/bin/env python3
"""Insere (idempotente) as chaves i18n da v0.7.11-web44 nos 5 idiomas.

Cobre: botão jump com contador, excluir/ordenar no explorador e filtros +
aviso de contexto incompatível no seletor de modelos.

Roda: python3 scripts/add_i18n_web44.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / "pesquisai" / "webui" / "i18n.json"

NEW = {
    "pt-BR": {
        "jump.toLast": "Ir para a última mensagem",
        "jump.newMessages": "{n} novas mensagens",
        "explorer.delete": "Excluir",
        "explorer.deleteConfirm": "Excluir {name}? Esta ação não pode ser desfeita.",
        "explorer.deleteDirConfirm": "Excluir a pasta {name} e todo o seu conteúdo? Esta ação não pode ser desfeita.",
        "explorer.deleteFail": "Não foi possível excluir",
        "explorer.deleted": "Excluído: {name}",
        "explorer.sort": "Ordenar",
        "explorer.sortName": "Nome (A→Z)",
        "explorer.sortNameDesc": "Nome (Z→A)",
        "explorer.sortNewest": "Mais recentes",
        "explorer.sortOldest": "Mais antigos",
        "model.freeOnly": "Só grátis",
        "model.availableOnly": "Com chave",
        "model.allProviders": "Todos os provedores",
        "model.byProvider": "Filtrar por provedor",
        "model.incompatible": "incompatível",
        "model.incompatibleTip": "Janela de {k} — abaixo do mínimo de {min}k exigido pelo UFVAI",
        "model.none": "nenhum modelo encontrado",
    },
    "en": {
        "jump.toLast": "Go to the latest message",
        "jump.newMessages": "{n} new messages",
        "explorer.delete": "Delete",
        "explorer.deleteConfirm": "Delete {name}? This cannot be undone.",
        "explorer.deleteDirConfirm": "Delete the folder {name} and all its contents? This cannot be undone.",
        "explorer.deleteFail": "Could not delete",
        "explorer.deleted": "Deleted: {name}",
        "explorer.sort": "Sort",
        "explorer.sortName": "Name (A→Z)",
        "explorer.sortNameDesc": "Name (Z→A)",
        "explorer.sortNewest": "Newest first",
        "explorer.sortOldest": "Oldest first",
        "model.freeOnly": "Free only",
        "model.availableOnly": "Has key",
        "model.allProviders": "All providers",
        "model.byProvider": "Filter by provider",
        "model.incompatible": "incompatible",
        "model.incompatibleTip": "{k} context — below the {min}k minimum required by UFVAI",
        "model.none": "no model found",
    },
    "es": {
        "jump.toLast": "Ir al último mensaje",
        "jump.newMessages": "{n} mensajes nuevos",
        "explorer.delete": "Eliminar",
        "explorer.deleteConfirm": "¿Eliminar {name}? Esta acción no se puede deshacer.",
        "explorer.deleteDirConfirm": "¿Eliminar la carpeta {name} y todo su contenido? Esta acción no se puede deshacer.",
        "explorer.deleteFail": "No se pudo eliminar",
        "explorer.deleted": "Eliminado: {name}",
        "explorer.sort": "Ordenar",
        "explorer.sortName": "Nombre (A→Z)",
        "explorer.sortNameDesc": "Nombre (Z→A)",
        "explorer.sortNewest": "Más recientes",
        "explorer.sortOldest": "Más antiguos",
        "model.freeOnly": "Solo gratis",
        "model.availableOnly": "Con clave",
        "model.allProviders": "Todos los proveedores",
        "model.byProvider": "Filtrar por proveedor",
        "model.incompatible": "incompatible",
        "model.incompatibleTip": "Ventana de {k} — por debajo del mínimo de {min}k exigido por UFVAI",
        "model.none": "ningún modelo encontrado",
    },
    "fr": {
        "jump.toLast": "Aller au dernier message",
        "jump.newMessages": "{n} nouveaux messages",
        "explorer.delete": "Supprimer",
        "explorer.deleteConfirm": "Supprimer {name} ? Cette action est irréversible.",
        "explorer.deleteDirConfirm": "Supprimer le dossier {name} et tout son contenu ? Cette action est irréversible.",
        "explorer.deleteFail": "Impossible de supprimer",
        "explorer.deleted": "Supprimé : {name}",
        "explorer.sort": "Trier",
        "explorer.sortName": "Nom (A→Z)",
        "explorer.sortNameDesc": "Nom (Z→A)",
        "explorer.sortNewest": "Plus récents",
        "explorer.sortOldest": "Plus anciens",
        "model.freeOnly": "Gratuits seulement",
        "model.availableOnly": "Avec clé",
        "model.allProviders": "Tous les fournisseurs",
        "model.byProvider": "Filtrer par fournisseur",
        "model.incompatible": "incompatible",
        "model.incompatibleTip": "Fenêtre de {k} — en dessous du minimum de {min}k requis par UFVAI",
        "model.none": "aucun modèle trouvé",
    },
    "zh": {
        "jump.toLast": "跳到最新消息",
        "jump.newMessages": "{n} 条新消息",
        "explorer.delete": "删除",
        "explorer.deleteConfirm": "删除 {name}？此操作无法撤销。",
        "explorer.deleteDirConfirm": "删除文件夹 {name} 及其全部内容？此操作无法撤销。",
        "explorer.deleteFail": "无法删除",
        "explorer.deleted": "已删除：{name}",
        "explorer.sort": "排序",
        "explorer.sortName": "名称（A→Z）",
        "explorer.sortNameDesc": "名称（Z→A）",
        "explorer.sortNewest": "最新优先",
        "explorer.sortOldest": "最早优先",
        "model.freeOnly": "仅免费",
        "model.availableOnly": "有密钥",
        "model.allProviders": "所有提供商",
        "model.byProvider": "按提供商筛选",
        "model.incompatible": "不兼容",
        "model.incompatibleTip": "上下文 {k} — 低于 UFVAI 要求的最小值 {min}k",
        "model.none": "未找到模型",
    },
}


def main() -> int:
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    locales = data.setdefault("locales", {})
    added = 0
    for lang, values in NEW.items():
        bucket = locales.setdefault(lang, {})
        for key, value in values.items():
            if key not in bucket:
                bucket[key] = value
                added += 1
    data["version"] = "0.7.11-web44"
    TARGET.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"i18n web44: {added} chaves adicionadas; versão -> {data['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
