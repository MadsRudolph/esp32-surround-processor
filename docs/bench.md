# Bench

Paths in backticks are relative to the repository root, and commands are run from there.
Back to the [README](../README.md).

Bring-up runs from a local page that is both the test procedure and the Analog
Discovery 3's display: live scope on both rails (DC and a high-resolution ripple view),
rail check, ripple, a rail watch for brown-outs, and a UART console on J2 TX. Start it
and open <http://127.0.0.1:8791/>:

```bash
python3 tools/bench_server.py
```

The server owns the AD3 (close WaveForms first, or press *Release AD3* on the page to
hand it back). Results are saved to `hardware/bench/results.json`; *Reset run* archives
them in `hardware/bench/runs/`. The steps are one array, `STEPS`, at the top of the
script in `tools/bench_page.html`. `tools/bench.py` still does the same checks from the
terminal when the server is not running.
