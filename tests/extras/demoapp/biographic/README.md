# Biographic demo scripts

End-to-end biographic API demo for Country Workspace. Requires `httpie`, `jq`, `python3`, and `column`.

```console
./use_base_url http://localhost:8000
./use_auth_token <token with API_BIOGRAPHIC grant>
./full_flow [business_area] [program_code]
```

`full_flow` checks deduplication against an approved population (400 people), soft-deletes and recreates the program, then verifies that the new group starts with an empty population. It approves a replacement population with distinct `POP2-` reference PKs and checks that a new registration matches only that population. Expected results are **7 population + 2 batch**, **0 population + 2 batch**, then **7 population + 2 batch** duplicates.

Use a fresh program code for each run. For manual steps, use `use_program`, `create_dataset`, `delete_program`, and the other scripts.

See the [demo guide](../../../../docs/src/biographic/development/demo.md) for the full workflow and examples.
