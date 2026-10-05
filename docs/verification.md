# Publication verification

Checked on October 5, 2026 in a fresh Python 3.12 environment with the project's dev, UI, and plotting extras installed:

- 54 pytest tests passed with the generated sample-file directory absent. The UI and CLI share the same in-memory synthetic sample builder.
- Ruff passed on source, tests, UI and examples.
- The music-creator example completed.
- The README figure was generated from invented data with known effects. The generator is checked in as `examples/music_creator/plot_effects.py`.

The figure demonstrates a synthetic example, not causal results on a social platform. CI repeats tests, lint and the example under Python 3.11, 3.12 and 3.13.
