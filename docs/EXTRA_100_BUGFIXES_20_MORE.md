# TouchStation Extra — 20 additional bug fixes

This pass hardens the game-library companion, document inspection, save backup/restore and session tracking. It does not change the native PS3 engine.

1. game-ID key collisions — append a SHA-256-derived suffix to the readable game-ID key.
2. legacy metadata recovery — read existing pre-hash keys when the new key is absent.
3. legacy key migration — move old metadata and status history before removing old preference keys.
4. original title-ID preservation — store the raw title ID separately from the preference-key encoding.
5. metadata size limits — cap title, category, tags, status and note fields.
6. status-history consistency — write updated metadata and status history through one SharedPreferences editor.
7. document-prefix zero-read handling — avoid a tight loop if a provider returns a zero-length read.
8. disc-marker zero-read handling — apply the same guard to ISO/UDF descriptor sampling.
9. SHA-256 zero-read handling — advance or finish safely when a stream returns zero bytes.
10. copy-stream zero-read handling — copy a single byte rather than spinning on a zero-length read.
11. same-document copy protection — reject identical source and destination URIs before opening the destination in truncate mode.
12. copy byte-count overflow protection — detect Long overflow rather than reporting a negative byte count.
13. partial-copy cleanup — remove the newly created destination if copying or checksum verification fails.
14. persist game-file read permission — retain Storage Access Framework permission when possible.
15. persist save-source permission — retain selected save-file read access across app restarts when Android grants it.
16. persist restore-source permission — retain selected backup read access across app restarts when possible.
17. permission failure clarity — tell the user when a selected document has only temporary access.
18. session timer keying — restart/cancel the timer effect when the selected game ID changes.
19. playtime total overflow protection — use saturating addition for accumulated and displayed playtime.
20. stale elapsed-time reset — clear the live elapsed counter when starting or stopping a tracked session.

All file transfers remain user-selected and checksum-verified. A failed transfer reports an error and attempts to remove the partial destination. Android document providers may not support deletion, so cleanup is best-effort.