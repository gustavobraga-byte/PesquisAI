/**
 * Google Apps Script — Webhook de Contatos UFVAI v0.6.11
 *
 * Este script recebe POSTs do UFVAI (opt-in de contato + heartbeat de
 * acesso ativo) e grava na planilha "Contatos UFVAI" do seu Google Drive.
 *
 * v0.6.10: adiciona colunas Nome (ao lado do e-mail) e IP do cliente.
 * v0.6.11: descoberta automática do backend (app Android só-Nuvem, sem colar
 * URL). O Colab anuncia sua URL pública (proxyPort) via POST com `backend_url`
 * (flag `backend_online`); o script guarda como "último backend" por usuário
 * (ScriptProperties, chave = sha do e-mail) e serve via GET:
 * `.../exec?action=backend&email_sha256=...` → `{"ok":true,"backend_url":...}`.
 * Só o próprio usuário (pelo sha do e-mail) recupera sua URL; nenhuma linha da
 * planilha é exposta. 100% compatível com o comportamento anterior.
 *
 * Payload esperado:
 *   {
 *     "product": "ufvai",
 *     "email": "usuario@dominio.br",
 *     "name": "Nome da Pessoa",
 *     "email_sha256": "abc123...",
 *     "ip": "200.1.2.3",
 *     "environment": "colab" | "local",
 *     "app_version": "0.6.10",
 *     "sent_at": "2026-09-01T13:45:00",
 *     "flag": "usuario_ativo"
 *   }
 * v0.6.20 (contrato final, 01/10/2026): a planilha recebe EXATAMENTE UMA
 * linha por ativação/retorno — flag "usuario_ativo" (e-mail · nome · IP),
 * disparada quando o usuário clica no botão (Continuar/ABRIR → /api/access).
 * O primeiro aceite NÃO grava linha "novo_contato"; a flag legada ainda é
 * aceita (compatibilidade) pela validação abaixo.
 *
 * SEGURANÇA:
 * - Não usa planilha compartilhada (removido P0 #3)
 * - O endpoint (/exec) é público mas NÃO expõe dados existentes
 * - Validação básica: produto deve ser "ufvai", email obrigatório
 * - Limite de 1000 entradas (anti-abuso) → aumentado para 5000 na v0.6.10
 *
 * COMO INSTALAR / ATUALIZAR:
 * 1. Abra https://script.google.com (projeto já implantado)
 * 2. Substitua TODO o código por esta versão v0.6.11 (a URL /exec NÃO muda)
 * 3. Se a aba "Contatos" já existe com cabeçalho antigo (6 colunas), este
 *    script migra automaticamente: insere colunas Nome e IP e preserva dados.
 * 4. Salve (Ctrl+S) → Implantar → Gerenciar implantação → Editar → Nova versão → Implantar
 *    (mantém a mesma URL /exec — nada a reconfigurar no UFVAI)
 * 6. URL /exec configurada em:
 *    export UFVAI_CONTACT_ENDPOINT="https://script.google.com/macros/s/SEU_ID/exec"
 */

const SPREADSHEET_ID = "1TWVuKtApnuzrW59ZYymnjLTgMXa1Exo0XAZQHSfwoqE";
const SHEET_NAME = "Contatos";
const MAX_ROWS = 5000;

function doPost(e) {
  try {
    // Parse do body JSON
    const data = JSON.parse(e.postData.contents);

    // Validação básica
    if (!data.email || !data.email.includes("@")) {
      return ContentService.createTextOutput(
        JSON.stringify({ ok: false, error: "email inválido" })
      ).setMimeType(ContentService.MimeType.JSON);
    }

    if (data.product !== "ufvai") {
      return ContentService.createTextOutput(
        JSON.stringify({ ok: false, error: "produto inválido" })
      ).setMimeType(ContentService.MimeType.JSON);
    }

    // Abre a planilha
    const ss = SpreadsheetApp.openById(SPREADSHEET_ID);
    let sheet = ss.getSheetByName(SHEET_NAME);

    // Cria a aba se não existir — cabeçalho v0.6.10 com Nome e IP
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow([
        "Timestamp",
        "Email",
        "Nome",
        "Email SHA-256",
        "Ambiente",
        "Versão",
        "Flag",
        "IP",
      ]);
      // congela cabeçalho + formatação básica
      sheet.setFrozenRows(1);
      sheet.getRange(1,1,1,8).setFontWeight("bold").setBackground("#1F3864").setFontColor("#FFFFFF");
      sheet.setColumnWidth(1, 170); // Timestamp
      sheet.setColumnWidth(2, 220); // Email
      sheet.setColumnWidth(3, 160); // Nome
      sheet.setColumnWidth(4, 220); // SHA
      sheet.setColumnWidth(5, 90);  // Ambiente
      sheet.setColumnWidth(6, 70);  // Versão
      sheet.setColumnWidth(7, 120); // Flag
      sheet.setColumnWidth(8, 110); // IP
    } else {
      // Migração automática de cabeçalho antigo (v0.6.9: 6 colunas) → v0.6.10 (8 colunas)
      var header = sheet.getRange(1,1,1,Math.min(sheet.getLastColumn(), 8)).getValues()[0].join("|");
      if (header.indexOf("Nome") === -1 || header.indexOf("IP") === -1) {
        // preserva dados existentes: insere colunas 3 (Nome) e 8 (IP) se faltarem
        var lastCol = sheet.getLastColumn();
        // se só tem 6 colunas → precisa expandir para 8
        if (lastCol === 6) {
          // Insere "Nome" após Email (col 3) — desloca SHA etc para direita
          sheet.insertColumnAfter(2);
          sheet.getRange(1,3).setValue("Nome");
          // Agora tem 7 cols, insere IP no fim (col 8)
          sheet.getRange(1,8).setValue("IP");
          // re-aplica cabeçalho
          sheet.getRange(1,1,1,8).setFontWeight("bold").setBackground("#1F3864").setFontColor("#FFFFFF");
        } else if (lastCol === 7 && header.indexOf("IP") === -1) {
          sheet.getRange(1,8).setValue("IP");
        }
      }
    }

    // Limite anti-abuso
    if (sheet.getLastRow() > MAX_ROWS) {
      return ContentService.createTextOutput(
        JSON.stringify({ ok: false, error: "limite de cadastros atingido" })
      ).setMimeType(ContentService.MimeType.JSON);
    }

    // v0.6.9: flag distingue novo contato (opt-in) de usuário já ativo
    // (reabertura — tela "Bem-vindo de volta" → email + hora + flag)
    // v0.6.11: flag backend_online = anúncio da URL pública (descoberta do app)
    var flag = String(data.flag || "novo_contato");
    if (flag !== "novo_contato" && flag !== "usuario_ativo"
        && flag !== "backend_online") { flag = "novo_contato"; }

    // v0.6.10: nome e ip
    var nome = String(data.name || data.nome || "").trim().substring(0, 100);
    var ip = String(data.ip || "").trim().substring(0, 45); // IPv6 max 45 chars

    // v0.6.11: anúncio de backend — guarda "último backend" deste usuário
    // (chave = sha do e-mail; sem PII além do que o POST já traz). Melhor
    // esforço: se falhar, a linha de auditoria abaixo segue normalmente.
    var backendUrl = String(data.backend_url || "").trim().substring(0, 300);
    if (backendUrl && /^https?:\/\//i.test(backendUrl)) {
      flag = "backend_online";
      try {
        var keySha = data.email_sha256 && String(data.email_sha256).trim()
          ? String(data.email_sha256).trim().toLowerCase()
          : shaHex(String(data.email).trim().toLowerCase());
        getProps().setProperty("ufvai_backend_" + keySha, JSON.stringify({
          url: backendUrl.replace(/\/+$/, "") + "/",
          at: new Date().toISOString(),
        }));
      } catch (errProps) { /* segue para a linha de auditoria */ }
    }

    // Grava a linha — ordem v0.6.10 com Nome e IP
    // v0.6.20-fix: "Versão" é gravada APÓS o appendRow, célula a célula com
    // formato texto ("@") — sem isso o Sheets converte "0.6.20" em DATA e a
    // planilha exibe "2000.6.20". As demais colunas mantêm o appendRow normal
    // (Timestamp continua virando datetime, ordenável).
    sheet.appendRow([
      data.sent_at || new Date().toISOString(),
      data.email,
      nome,
      data.email_sha256 || "",
      data.environment || "",
      "", // Versão — gravada logo abaixo como TEXTO (coluna F)
      flag,
      ip,
    ]);
    try {
      var _newRow = sheet.getLastRow();
      var _vCell = sheet.getRange(_newRow, 6);
      _vCell.setNumberFormat("@");
      _vCell.setValue(String(data.app_version || ""));
    } catch (eVer) { /* segue — versão ausente não deve barrar o registro */ }

    return ContentService.createTextOutput(
      JSON.stringify({ ok: true, message: "Contato registrado" })
    ).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({ ok: false, error: "Erro interno: " + err })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * GET: verificação de saúde + descoberta do backend (v0.6.11).
 * `.../exec` → {"ok":true,"service":...,"version":"0.6.11"}
 * `.../exec?action=backend&email_sha256=...` (ou &email=...) →
 *   {"ok":true,"backend_url":"...","updated_at":"..."} ou {"ok":false,...}.
 * Só devolve o backend do próprio solicitante (pelo sha); nada da planilha.
 */
function doGet(e) {
  try {
    var p = (e && e.parameter) || {};
    if (String(p.action || "") === "backend") {
      var sha = String(p.email_sha256 || "").trim().toLowerCase();
      if (!sha && p.email) {
        sha = shaHex(String(p.email).trim().toLowerCase());
      }
      if (!sha) {
        return jsonOut({ ok: false, error: "informe email_sha256" });
      }
      var raw = getProps().getProperty("ufvai_backend_" + sha);
      if (!raw) {
        return jsonOut({ ok: false, error: "not_found" });
      }
      var rec = JSON.parse(raw);
      return jsonOut({ ok: true, backend_url: rec.url, updated_at: rec.at });
    }
  } catch (err) {
    return jsonOut({ ok: false, error: "Erro interno: " + err });
  }
  return jsonOut({ ok: true, service: "UFVAI Contact Webhook", version: "0.6.11" });
}

function jsonOut(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function getProps() {
  return PropertiesService.getScriptProperties();
}

function shaHex(s) {
  var d = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256, s, Utilities.Charset.UTF_8);
  var h = "";
  for (var i = 0; i < d.length; i++) {
    var v = (d[i] < 0 ? d[i] + 256 : d[i]).toString(16);
    h += v.length === 1 ? "0" + v : v;
  }
  return h;
}
