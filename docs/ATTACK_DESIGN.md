# Attack design decisions

- Attacker node 8 is a mid-path client with descendants in the established baseline topology.
- A dedicated UDP attack port prevents the flood packets from corrupting normal request/response counters.
- Attack logic is compiled into all clients, but activates only when `node_id == 8`.
- Baseline and impairment firmware remain unchanged and retain their original hashes.
- Stage 2 will add a topology-manipulation attack and a forwarding/drop attack after Stage-1 pilots are validated.
