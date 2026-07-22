"""QuorumQA Recursive RAG -- v1 retrieval stack (phase G0).

See docs/recursive-rag-plan.md for the full design (R1-R4, the integrity
firewall in section 4, and the Appendix A technique verdicts this stack
follows). This package only builds the G0 substrate: corpus + hybrid index
+ the `search_corpus` MCP tool. Wiring it into the Verifier's tool rack
behind a flag (R1/R2) is a later phase -- nothing here changes engine
behavior yet.
"""
