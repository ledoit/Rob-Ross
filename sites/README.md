# Site consumers

Downstream apps that receive palette tokens from Rob-Ross. **Not part of the genome.**

Register each app in `consumers.json`:

```json
"my-app": {
  "label": "Human name",
  "format": "typescript_paid",
  "path": "../../Sync/MyApp/src/lib/themes.ts"
}
```

Paths are relative to the Rob-Ross repo root.

## Move an app (e.g. Paid → Sync)

1. `git clone git@github.com:ledoit/paid.git` into `Menhir Holdings/Sync/Paid`
2. Update **only** `sites/consumers.json` → `"path": "../../Sync/Paid/src/lib/themes.ts"`
3. From Rob-Ross: `python cli.py web sync paid`
4. Remove the old folder (e.g. `Employment/Paid`) after verifying sync
5. Commit both repos — no changes required inside the app except auto-generated `themes.ts`

Coupling is one registry entry + `web sync`. No genome edits.
