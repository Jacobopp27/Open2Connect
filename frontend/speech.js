/* Browser speech adapter; injected browser APIs make lifecycle behavior testable. */
class O2CSpeech {
  constructor({Recognition, synthesis, Utterance, onState, onText, onEnd}) {
    this.Recognition = Recognition;
    this.synthesis = synthesis;
    this.Utterance = Utterance;
    this.onState = onState || (() => {});
    this.onText = onText || (() => {});
    this.onEnd = onEnd || (() => {});
    this.recognition = null;
    this.paused = false;
    this.finalText = '';
  }
  speak(text, locale) {
    if (!this.synthesis || !this.Utterance) return false;
    this.synthesis.cancel();
    const utterance = new this.Utterance(text);
    utterance.lang = locale === 'en' ? 'en-US' : 'es-CO';
    this.synthesis.speak(utterance);
    return true;
  }
  listen(locale) {
    if (!this.Recognition) { this.onState('unsupported'); return false; }
    if (this.recognition) return false;
    this.synthesis?.cancel(); // User interruption of spoken question.
    this.paused = false;
    this.finalText = '';
    this.lastError = '';
    const r = new this.Recognition();
    this.recognition = r;
    r.lang = locale === 'en' ? 'en-US' : 'es-CO';
    r.continuous = false;
    r.interimResults = true;
    r.onstart = () => this.onState('listening');
    r.onspeechstart = () => this.onState('speech');
    r.onspeechend = () => this.onState('speech-ended');
    r.onresult = event => {
      let final = '', interim = '';
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) final += event.results[i][0].transcript;
        else interim += event.results[i][0].transcript;
      }
      this.finalText = final;
      this.onText(final + interim, Boolean(final));
    };
    r.onerror = e => { this.finalText = ''; this.lastError = 'error:' + e.error; this.onState(this.lastError); };
    r.onend = () => {
      this.recognition = null;
      this.onState(this.paused ? 'paused' : (this.lastError || 'idle'));
      if (!this.paused && this.finalText.trim()) this.onEnd(this.finalText.trim());
    };
    try { r.start(); return true; }
    catch (_) { this.recognition = null; this.onState('error:start'); return false; }
  }
  finish() { this.recognition?.stop(); }
  pause() {
    this.paused = true;
    this.synthesis?.cancel();
    this.recognition?.abort();
    this.onState('paused');
  }
  dispose() {
    this.pause();
    if (this.recognition) {
      this.recognition.onresult = null;
      this.recognition.onend = null;
      this.recognition.onerror = null;
      this.recognition = null;
    }
  }
}
if (typeof module !== 'undefined') module.exports = O2CSpeech;
else window.O2CSpeech = O2CSpeech;
