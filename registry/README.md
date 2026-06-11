# Registry (runtime state)

Ephemeral workflow state — **not** the genome.

| File | Purpose |
|------|---------|
| `theme_roster.json` | Palette ids you kept for export |
| `ide_iteration_session.json` | Current draft + iteration chain |
| `user_loop_state.json` | Taste mood weights (optional learning) |

The genome **reads** the roster at generation time and builds a live color graph in memory (`core/live_genome.py`). Nothing here is taste DNA.
