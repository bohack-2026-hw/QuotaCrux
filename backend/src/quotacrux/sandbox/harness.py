"""In-container launcher. Compiles the candidate, signals readiness, then runs it as __main__.

The host starts timing only after the readiness marker, so interpreter and container startup are excluded.
"""

import sys

READY = b"QUOTACRUX_READY\n"
COMPILE_ERROR_EXIT = 97


def main():
    path = sys.argv[1]
    profile = len(sys.argv) > 2 and sys.argv[2] == "--profile"
    with open(path, "rb") as f:
        source = f.read()
    try:
        code = compile(source, "candidate.py", "exec")
    except (SyntaxError, ValueError) as exc:
        sys.stderr.write(f"QUOTACRUX_COMPILE_ERROR: {exc}\n")
        sys.stderr.flush()
        sys.exit(COMPILE_ERROR_EXIT)

    sys.stdout.buffer.write(READY)
    sys.stdout.buffer.flush()
    sys.argv = ["candidate.py"]
    namespace = {"__name__": "__main__", "__file__": "candidate.py", "__builtins__": __builtins__}
    if not profile:
        exec(code, namespace)
        sys.stdout.flush()
        return

    import cProfile
    import io
    import pstats

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        exec(code, namespace)
        sys.stdout.flush()
    finally:
        profiler.disable()
        buf = io.StringIO()
        pstats.Stats(profiler, stream=buf).sort_stats("cumulative").print_stats(25)
        sys.stderr.write("QUOTACRUX_PROFILE_BEGIN\n" + buf.getvalue() + "QUOTACRUX_PROFILE_END\n")
        sys.stderr.flush()


main()
