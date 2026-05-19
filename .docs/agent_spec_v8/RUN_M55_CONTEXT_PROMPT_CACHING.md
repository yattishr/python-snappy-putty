Implement M5.5 context/prompt caching for Snappy.

Add a cache layer that stores repo snapshot summaries and bounded context bundles under .snappy/cache/.

Cache keys should include:
- snapshot_id
- normalized user goal hash
- selected file hashes
- planner mode/version

Do not cache final plans.
Only cache reusable context inputs.

Update context discovery so package-lock.json is not treated as an entrypoint unless no better source/config file exists or the user goal is dependency/package related.

Split grounded planner prompt construction into stable_prefix and dynamic_payload so repeated planner instructions and schema remain byte-identical across calls.

Add tests proving:
1. repeated planning on unchanged snapshot reuses cached context
2. changed file hash invalidates context cache
3. package-lock.json is not selected as entrypoint for vanilla Node API route/spec goals
4. generated planner payload is smaller on repeated calls
5. cache can be disabled via config/env for debugging
