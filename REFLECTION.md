# Privacy & Limitations Reflection

## PII Risks

The LongTermProfile stores personal information such as names, ages, allergies, and preferences directly in `data/profile.json` as plain-text JSON. This poses several privacy risks:

- **Unencrypted storage**: All profile data is stored in plaintext on disk. Anyone with file access can read user facts including health information (allergies).
- **No access control**: There is no authentication or authorization mechanism. Any process or user can read or modify the profile file.
- **Health data sensitivity**: Allergy information constitutes health data under regulations like HIPAA and GDPR. Storing this without proper safeguards may violate data protection laws.
- **No consent tracking**: The system automatically extracts and stores personal facts without explicit user consent or disclosure about what is being stored.

## Deletion Procedure

To delete a user's data:

1. Clear the in-memory `LongTermProfile._data` dictionary
2. Delete `data/profile.json` (overwrites with empty `{}`
)
3. Delete `data/episodes.json` (overwrites with `[]`)
4. The `ShortTermMemory` lives in-process and is cleared when the session ends
5. `knowledge_base.json` contains no personal data and does not need deletion

This is a manual process with no API endpoint or automated data deletion mechanism. A production system would need a GDPR-compliant right-to-erasure endpoint.

## Scaling Limitations

1. **No TTL (Time-To-Live)**: Memories persist indefinitely with no expiration. Stale facts (e.g., a changed address or outdated preference) remain until explicitly overwritten. There is no automatic pruning of outdated information.

2. **No thread safety**: All memory backends use file I/O with no locking mechanism. Concurrent access from multiple agent instances would cause race conditions and data corruption. A production system needs database-backed storage with proper transaction support.

3. **Keyword search degrades at scale**: The `EpisodicMemory` and `SemanticMemory` use simple keyword matching. This approach:
   - Scales linearly (O(n)) with data size
   - Misses semantic matches that use different wording
   - Cannot handle typos or synonyms
   - Should be replaced with vector embeddings (FAISS, Pinecone) for production use

4. **No versioning or audit trail**: Profile updates overwrite previous values with no history. If a conflict resolution is incorrect, the previous value is lost permanently.

5. **Memory budget is character-based, not token-based**: The 2000-character budget approximation may not accurately reflect actual token costs for LLM APIs, potentially wasting context window space or exceeding limits.

6. **Single-user assumption**: All memory stores assume a single user profile. Multi-user scenarios would require session isolation and user identification.