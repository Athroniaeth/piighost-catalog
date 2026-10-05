/// <reference lib="webworker" />

/**
 * piighost's regex pipeline, running in the visitor's own tab.
 *
 * The playground sends its text to the API, which is honest about not storing
 * it but is still a promise rather than a property. Here the text does not
 * leave: Pyodide loads the real `piighost` wheel, which is pure Python and
 * needs only `typing-extensions` at its core, and the same `RegexDetector` and
 * `ConfidenceOverlapResolver` the registry's own checks use do the work.
 *
 * Running it faithfully is the whole point, and it rules out the obvious
 * shortcut. These patterns are Python `re` compiled with `re.ASCII`: JavaScript
 * disagrees on lookbehind, on what `\w` covers and on how a quantifier
 * backtracks, so a regex engine that is merely similar would report detections
 * the registry does not make.
 *
 * In a worker because loading Pyodide takes seconds and a hostile pattern can
 * take longer still; neither may hold the page.
 */

import { loadPyodide, type PyodideInterface } from "pyodide";

type Ready = { type: "ready" };
type Failed = { type: "failed"; error: string };
type Ran = { type: "ran"; hits: Hit[]; elapsedMs: number };

export type Hit = { label: string; start: number; end: number; text: string };
export type ToWorker =
  | { type: "start" }
  | { type: "run"; patterns: Record<string, string>; text: string };
export type FromWorker = Ready | Failed | Ran;

/** Where the assets are served from, same origin, by the build step. */
const ASSETS = "/pyodide/";
const WHEEL = "piighost-2.0.0-py3-none-any.whl";

/**
 * Unpack a pure-Python wheel into the virtual filesystem.
 *
 * micropip would do this and would also reach PyPI, which `connect-src 'self'`
 * forbids. A wheel is a zip, piighost is pure Python, and its core needs
 * nothing but the standard library, so unzipping it where Python looks is the
 * whole installation.
 */
const INSTALL = `
import io, site, sys, zipfile

def install(payload):
    target = site.getsitepackages()[0]
    with zipfile.ZipFile(io.BytesIO(bytes(payload))) as wheel:
        wheel.extractall(target)
    if target not in sys.path:
        sys.path.insert(0, target)
`;

/** The pipeline, written once here rather than assembled call by call. */
const RUNNER = `
import json, time
from piighost.components.detector import RegexDetector
from piighost.components.overlap_resolver.confidence import ConfidenceOverlapResolver

_resolver = ConfidenceOverlapResolver()

async def run(patterns_json, text):
    """Detect, resolve the overlaps, and hand back what survived.

    Async all the way down: piighost's detect is a coroutine, and Pyodide
    cannot drive an event loop from a synchronous entry point. Awaited from
    JavaScript, where the coroutine arrives as a promise.
    """
    patterns = json.loads(patterns_json)
    started = time.perf_counter()
    detector = RegexDetector(patterns=patterns)
    found = await detector.detect(text)
    kept = _resolver.resolve(found)
    elapsed = (time.perf_counter() - started) * 1000
    return json.dumps({
        "hits": [
            {"label": h.label, "start": h.span.start, "end": h.span.end, "text": h.text}
            for h in sorted(kept, key=lambda h: h.span.start)
        ],
        "elapsed": elapsed,
    })
`;

let python: PyodideInterface | null = null;
/** Held rather than fetched per call: a proxy taken and destroyed each time is
 *  one more thing to get wrong, and this one lives as long as the worker. */
let runner: ((patterns: string, text: string) => Promise<string>) | null = null;

async function start(): Promise<void> {
  if (python) return;
  const runtime = await loadPyodide({ indexURL: ASSETS });
  const wheel = await fetch(`${ASSETS}${WHEEL}`);
  if (!wheel.ok) throw new Error(`${WHEEL}: ${wheel.status}`);
  runtime.runPython(INSTALL);
  runtime.globals.get("install")(new Uint8Array(await wheel.arrayBuffer()));
  runtime.runPython(RUNNER);
  runner = runtime.globals.get("run");
  python = runtime;
}

function post(message: FromWorker) {
  (self as unknown as DedicatedWorkerGlobalScope).postMessage(message);
}

self.onmessage = async (event: MessageEvent<ToWorker>) => {
  try {
    if (event.data.type === "start") {
      await start();
      post({ type: "ready" });
      return;
    }
    await start();
    // Awaited: `run` is a coroutine on the Python side, which arrives here as a
    // promise. Pyodide cannot drive an event loop from a synchronous call.
    const answer = JSON.parse(
      await runner!(JSON.stringify(event.data.patterns), event.data.text),
    );
    post({ type: "ran", hits: answer.hits, elapsedMs: answer.elapsed });
  } catch (caught) {
    post({ type: "failed", error: String(caught) });
  }
};
