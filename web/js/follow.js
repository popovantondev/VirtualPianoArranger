// Practice logic ("Follow"): the next token waits for the right key(s).
// Port of the Follow code in docs/design/dark.js. Pure: the time of every key press is passed in.

export const CHORD_WINDOW_MS = 300; // all notes of a chord must be pressed within this time

export class Follow {
  // tokens: [{notes: number[]}]. Tokens without notes are passed over.
  constructor(tokens) {
    this.tokens = tokens.map((token) => token.notes);
    this._recent = new Map();
    this.reset(0);
  }

  get cursor() {
    return this._cursor;
  }

  get done() {
    return this._cursor >= this.tokens.length;
  }

  reset(index = 0) {
    this._cursor = Math.max(0, Math.min(this.tokens.length, index));
    this._recent.clear();
    this._skipEmpty();
  }

  _skipEmpty() {
    while (this._cursor < this.tokens.length && !this.tokens[this._cursor].length) this._cursor++;
  }

  // The cursor token is completed by this press (all its notes pressed within the chord window).
  _completes(midi) {
    const required = this.tokens[this._cursor];
    return required.includes(midi) && required.every((note) => this._recent.has(note));
  }

  // action: "step" (next token), "wait" (wrong key, cursor stays),
  // "partial" (part of the current chord), "done" (the last token is finished).
  // Moving ahead without playing is only possible by clicking a token (reset).
  press(midi, nowMs) {
    if (this.done) return { action: "done", cursor: this._cursor };
    for (const [note, at] of this._recent) if (nowMs - at > CHORD_WINDOW_MS) this._recent.delete(note);
    this._recent.set(midi, nowMs);
    if (this._completes(midi)) {
      this._cursor += 1;
      this._recent.clear();
      this._skipEmpty();
      return { action: this.done ? "done" : "step", cursor: this._cursor };
    }
    const partial = this.tokens[this._cursor].includes(midi);
    return { action: partial ? "partial" : "wait", cursor: this._cursor };
  }
}
