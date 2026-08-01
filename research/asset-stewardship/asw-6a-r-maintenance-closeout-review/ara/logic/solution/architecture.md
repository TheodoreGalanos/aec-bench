# ASW-6A-R architecture

The source world remains the production pump-station world. A host selects one
committed snapshot and independently verifies the complete selected chain. The
review builder then reads the named Pump A records and the required reference
basis from that snapshot and history.

The builder publishes a separate content-addressed review case. Its public side
contains the named closeout pack, source snapshot reference, source record
references, reviewer role, and pack identity. Its private side contains the
issue specification, expected impact map, unaffected control set, and verifier
target. Preparation and issue-treatment receipts bind both sides without
changing the source world pointer or any source artifact.

The reviewer session exposes only observe, handover, and typed review
submission. Each action binds to the current case, pack, tenure, and source
records. The review repository publishes each accepted review immutably and
returns exact retries without duplicate records.

The independent verifier reloads the source world, proves the selected history
again, reconstructs the untreated and treated packs, checks their one declared
difference, and evaluates every required review field against the private
target. Direct, installed JSON, and local Harbor use these same task-owned
contracts and repository.
