"use client";
// Browser speech-to-text (Web Speech API, Chrome and Edge). Reports the whole running transcript
// on every change, which is what POST /v1/sessions/{id}/transcript expects.
import { useCallback, useRef, useState, useSyncExternalStore } from "react";

interface Alternative {
  transcript: string;
}
interface Result {
  isFinal: boolean;
  0: Alternative;
}
interface ResultEvent {
  results: ArrayLike<Result>;
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: ResultEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const noSubscribe = () => () => {};

export interface SpeechHandlers {
  /** The running transcript changed. `final` is true once no word is still being revised. */
  onTranscript: (text: string, final: boolean) => void;
  onError: (message: string) => void;
  /** Recognition stopped (pause, tap, or error); `text` is the last transcript. */
  onEnd: (text: string) => void;
}

export function useSpeech(lang = "en-IN") {
  // Known only in the browser; the static HTML renders the button disabled.
  const supported = useSyncExternalStore(noSubscribe, () => recognitionCtor() !== null, () => false);
  const [listening, setListening] = useState(false);
  const rec = useRef<Recognition | null>(null);

  const start = useCallback(
    (h: SpeechHandlers) => {
      const Ctor = recognitionCtor();
      if (!Ctor || rec.current) return;
      const r = new Ctor();
      let latest = "";
      r.lang = lang;
      r.interimResults = true;
      r.continuous = true;
      r.onresult = (e) => {
        let text = "";
        let final = true;
        for (const res of Array.from(e.results)) {
          text += res[0].transcript + " ";
          if (!res.isFinal) final = false;
        }
        latest = text.trim();
        h.onTranscript(latest, final);
      };
      r.onerror = (e) => h.onError(`Microphone: ${e.error}`);
      r.onend = () => {
        rec.current = null;
        setListening(false);
        h.onEnd(latest);
      };
      rec.current = r;
      setListening(true);
      r.start();
    },
    [lang],
  );

  const stop = useCallback(() => rec.current?.stop(), []);

  return { supported, listening, start, stop };
}
