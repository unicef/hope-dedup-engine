
# Biographic demo scripts

Drive the biographic API end to end, the way HOPE would. Requires `httpie`, `jq` and `python3`.

```console
$ ./use_base_url http://localhost:8000
$ ./use_auth_token <token with the API_BIOGRAPHIC grant>
$ ./full_flow [business_area] [program_code]
```

`full_flow` generates fake people, processes and approves a program's existing population, then deduplicates a
new registration against it and checks that every planted case (exact repeat, typo, sound-alike, nickname, namesake,
household member, duplicate within the batch, ...) comes out as expected.

## Create a dataset

`create_dataset` accepts an optional notification URL and a client-provided `dataset_id` (UUID).

Usage examples, the full scenario, and flow diagrams are available in the
[demo documentation](../../../../docs/src/biographic/development/demo.md).
