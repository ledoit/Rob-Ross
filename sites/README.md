# Site consumers

Downstream apps that receive palette tokens from Rob-Ross. **Not part of the genome.**

Register each app in `consumers.json`:

```json
"my-app": {
  "label": "Human name",
  "format": "typescript_paid",
  "path": "../../Flow/MyApp/src/lib/themes.ts"
}
```

Paths are relative to the Rob-Ross repo root.

## Move an app (e.g. Paid → Flow)

1. `git clone git@github.com:ledoit/paid.git` into `personal/Stonehenge/Flow/Paid`
2. Update **only** `sites/consumers.json` → `"path": "../../Flow/Paid/src/lib/themes.ts"`
3. From Rob-Ross: `python cli.py web sync paid`
4. Remove the old folder after verifying sync
5. Commit both repos — no changes required inside the app except auto-generated `themes.ts`

Coupling is one registry entry + `web sync`. No genome edits.
