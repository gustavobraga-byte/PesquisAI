/* voice.js — Integração do Assistente de Voz LFM3-Omni ao UFVAI Web.
 * Adiciona ditado por voz (ASR) e leitura das respostas (TTS) usando o
 * servidor local do assistente (porta 8010), sem depender de APIs de nuvem.
 */
(function () {
  const VOICE_API = 'http://127.0.0.1:8010';
  let mediaRecorder = null;
  let audioChunks = [];
  let recording = false;
  let audioPlayer = new Audio();

  function getSessionId() {
    // A sessão ativa fica no estado interno do app (exposto para integrações)
    if (window.__ufvai && window.__ufvai.state) {
      return window.__ufvai.state.sessionId || null;
    }
    return null;
  }

  async function checkVoiceServer() {
    try {
      const r = await fetch(VOICE_API + '/api/status', { signal: AbortSignal.timeout(2000) });
      const d = await r.json();
      return d.loaded;
    } catch (e) {
      return false;
    }
  }

  function updateMicState(active, busy) {
    const btn = document.getElementById('voice-mic-btn');
    if (!btn) return;
    if (active) {
      btn.style.color = '#ef4444';
      btn.style.animation = 'pulse 1s infinite alternate';
      btn.textContent = '⏹️';
      btn.title = 'Parar gravação e transcrever';
    } else {
      btn.style.color = busy ? '#eab308' : '';
      btn.style.animation = '';
      btn.textContent = '🎤';
      btn.title = 'Falar com o UFVAI (LFM3-Omni)';
    }
  }

  async function toggleRecording() {
    const btn = document.getElementById('voice-mic-btn');
    if (recording) {
      if (mediaRecorder) mediaRecorder.stop();
      return;
    }

    const online = await checkVoiceServer();
    if (!online) {
      alert('O servidor de voz (LFM3-Omni) não está respondendo na porta 8010.\n\nInicie-o com:\ncd agentes/lfm3-voz && python3 server.py');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = async () => {
        recording = false;
        updateMicState(false, true);
        stream.getTracks().forEach(t => t.stop());

        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        const fd = new FormData();
        fd.append('file', blob, 'audio.webm');

        const input = document.getElementById('input');
        const oldPlaceholder = input.placeholder;
        input.placeholder = 'Transcrevendo áudio localmente...';

        try {
          const res = await fetch(VOICE_API + '/api/transcribe', { method: 'POST', body: fd });
          const data = await res.json();
          if (data.text) {
            input.value = (input.value + ' ' + data.text).trim();
            input.dispatchEvent(new Event('input')); // ajusta altura do textarea
            // Envia automaticamente se o campo estava vazio antes do ditado
            if (window.__ufvaiVoiceAutoSend) {
              document.getElementById('send-btn')?.click();
            }
          } else if (data.error) {
            console.error('Erro ASR:', data.error);
          }
        } catch (e) {
          console.error('Falha na transcrição:', e);
        } finally {
          input.placeholder = oldPlaceholder;
          updateMicState(false, false);
        }
      };

      mediaRecorder.start();
      recording = true;
      updateMicState(true, false);
    } catch (e) {
      alert('Não foi possível acessar o microfone: ' + e.message);
    }
  }

  // Lê a última mensagem do assistente em voz alta
  async function speakLastMessage() {
    const msgs = document.querySelectorAll('.msg.assistant .msg-text, .message.assistant .text');
    if (!msgs.length) return;
    const text = msgs[msgs.length - 1].textContent;
    if (!text.trim()) return;

    try {
      const res = await fetch(VOICE_API + '/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.slice(0, 1000) })
      });
      if (res.ok) {
        const blob = await res.blob();
        audioPlayer.src = URL.createObjectURL(blob);
        audioPlayer.play();
      }
    } catch (e) {
      console.warn('TTS indisponível', e);
    }
  }

  // Inicialização
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('voice-mic-btn');
    if (btn) btn.addEventListener('click', toggleRecording);

    // Conversa ao vivo — abre o SELETOR de motor (Google Live ou LFM local).
    // Novo usuário NÃO deve cair direto no Gemini (v0.7.12-fix).
    const liveBtn = document.getElementById('voice-live-btn');
    if (liveBtn) {
      liveBtn.addEventListener('click', () => {
        window.open('/voz/start', '_blank', 'width=880,height=920');
      });
    }

    // Atalho: Ctrl+M para falar
    document.addEventListener('keydown', e => {
      if (e.ctrlKey && e.key === 'm') {
        e.preventDefault();
        toggleRecording();
      }
    });
  });
})();
