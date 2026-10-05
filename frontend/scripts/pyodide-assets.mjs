/**
 * Put Pyodide and the piighost wheel under `public/`, so the browser fetches
 * them from this origin.
 *
 * Not a convenience: the production Content-Security-Policy is `script-src
 * 'self'; connect-src 'self'`, which rules out Pyodide's CDN and rules out
 * micropip reaching PyPI. Everything the worker loads has to be served by us,
 * which also means a visitor who presses the test button gets a fixed version
 * rather than whatever PyPI resolves to that day.
 *
 * The wheel is downloaded rather than committed: 162 KB of build output does
 * not belong in the history, and the version is pinned here.
 */

import { createWriteStream } from "node:fs";
import { copyFile, mkdir, access } from "node:fs/promises";
import { dirname, join } from "node:path";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";
import { Readable } from "node:stream";

const here = dirname(fileURLToPath(import.meta.url));
const target = join(here, "..", "public", "pyodide");
const source = join(here, "..", "node_modules", "pyodide");

/** What the runtime loads: the module, the wasm, the stdlib and the lock. */
const RUNTIME = [
  "pyodide.mjs",
  "pyodide.asm.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide-lock.json",
];

const PIIGHOST = "2.0.0";
const WHEEL = `piighost-${PIIGHOST}-py3-none-any.whl`;
const WHEEL_URL = `https://pypi.org/pypi/piighost/${PIIGHOST}/json`;

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function main() {
  await mkdir(target, { recursive: true });
  for (const name of RUNTIME) {
    await copyFile(join(source, name), join(target, name));
  }

  const wheel = join(target, WHEEL);
  if (await exists(wheel)) {
    console.log(`pyodide assets ready, ${WHEEL} already downloaded`);
    return;
  }

  const meta = await (await fetch(WHEEL_URL)).json();
  const file = meta.urls.find((one) => one.filename === WHEEL);
  if (!file) throw new Error(`${WHEEL} is not on PyPI`);
  const response = await fetch(file.url);
  if (!response.ok) throw new Error(`${file.url}: ${response.status}`);
  await pipeline(Readable.fromWeb(response.body), createWriteStream(wheel));
  console.log(`pyodide assets ready, downloaded ${WHEEL}`);
}

await main();
