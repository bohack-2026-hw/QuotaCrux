"""Synthesise the sound effects track from the page's cue list (events.json -> sfx.wav, 48 kHz stereo).

Every cue is generated here from sine partials and seeded noise, so the track is reproducible and has no outside samples.
"""

import json
import sys
import wave

import numpy as np
from scipy.signal import lfilter

SR = 48000
rng = np.random.default_rng(20261114)


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def lowpass(x, cutoff):
    # one-pole low-pass, enough to soften noise
    a = np.exp(-2 * np.pi * cutoff / SR)
    return lfilter([1 - a], [1, -a], x)


def tone(freqs, dur, decay, attack=0.004, bright=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, f in enumerate(np.atleast_1d(freqs)):
        out += np.sin(2 * np.pi * f * t) * (0.8 ** k)
        out += bright * 0.25 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t / (decay * 0.4)) * (0.8 ** k)
    return out * env(n, attack, decay) / max(1, len(np.atleast_1d(freqs))) ** 0.5


def make(e):
    kind = e["type"]
    if kind == "tick":
        f = e.get("f", 1600)
        return tone(f, 0.05, 0.012, attack=0.0008, bright=0.4)
    if kind == "blip":
        return tone(e.get("f", 880), 0.25, 0.07, attack=0.003)
    if kind == "pop":
        n = int(0.09 * SR)
        t = np.arange(n) / SR
        f = 480 + 900 * t / 0.09
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.03)
    if kind == "chime":
        return tone(e.get("f", [880, 1320]), 1.8, 0.55, attack=0.002)
    if kind == "thud":
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        body = np.sin(2 * np.pi * (70 + 60 * np.exp(-t / 0.02)) * t) * env(n, 0.001, 0.07)
        knock = lowpass(rng.standard_normal(n), 1400) * env(n, 0.0005, 0.012) * 2.2
        return body + knock
    if kind == "whoosh":
        dur = max(0.15, e.get("dur", 0.6))
        n = int(dur * SR)
        t = np.arange(n) / SR
        shape = np.sin(np.pi * t / dur) ** 2
        raw = rng.standard_normal(n)
        swell = np.sin(np.pi * t / dur)
        noise = (lowpass(raw, 700) * (1 - swell) + lowpass(raw, 2600) * swell) * 2.6
        return noise * shape
    if kind == "rise":
        dur = e.get("dur", 1.0)
        n = int(dur * SR)
        t = np.arange(n) / SR
        f = 220 * (4 ** (t / dur))
        sweep = np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / dur) ** 1.5
        air = lowpass(rng.standard_normal(n), 2500) * (t / dur) ** 2 * 1.2
        return (sweep * 0.6 + air) * np.minimum(1, (dur - t) / 0.05)
    if kind == "buzz":
        n = int(0.42 * SR)
        t = np.arange(n) / SR
        x = np.sign(np.sin(2 * np.pi * 110 * t)) * 0.35 + np.sin(2 * np.pi * 116 * t) * 0.5
        return lowpass(x, 900) * env(n, 0.01, 0.16) * 1.4
    if kind == "impact":
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        boom = np.sin(2 * np.pi * (48 + 70 * np.exp(-t / 0.04)) * t) * env(n, 0.002, 0.28)
        hit = lowpass(rng.standard_normal(n), 2200) * env(n, 0.001, 0.03) * 1.5
        return boom + hit
    raise ValueError(kind)


def main(events_path, duration, out):
    events = json.load(open(events_path))
    n = int(duration * SR) + SR
    mix = np.zeros((n, 2))
    for e in events:
        x = make(e) * e.get("gain", 0.5)
        i = int(e["t"] * SR)
        if i >= n:
            continue
        x = x[: n - i]
        pan = float(np.clip(e.get("pan", 0), -1, 1))
        left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        mix[i : i + len(x), 0] += x * left * 1.414
        mix[i : i + len(x), 1] += x * right * 1.414
    mix = mix[: int(duration * SR)]
    # gentle soft clip, then normalise to -3 dBFS
    mix = np.tanh(mix * 1.2) / np.tanh(1.2)
    mix *= 10 ** (-3 / 20) / max(1e-9, np.abs(mix).max())
    pcm = (mix * 32767).astype("<i2")
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"{len(events)} cues -> {out} ({duration:.1f}s)")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), sys.argv[3])
