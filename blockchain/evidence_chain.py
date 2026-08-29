"""Blockchain module for evidence provenance tracking."""

import hashlib
import json
import time
from typing import List, Dict, Any


class EvidenceBlock:
    """A block in the evidence provenance chain."""

    def __init__(
        self,
        index: int,
        timestamp: float,
        evidence_hash: str,
        previous_hash: str,
        data: Dict[str, Any],
    ):
        self.index = index
        self.timestamp = timestamp
        self.evidence_hash = evidence_hash
        self.previous_hash = previous_hash
        self.data = data
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of the block."""
        block_string = json.dumps({
            'index': self.index,
            'timestamp': self.timestamp,
            'evidence_hash': self.evidence_hash,
            'previous_hash': self.previous_hash,
            'data': self.data,
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()


FIXED_TIMESTAMP = 1704067200.0  # 2024-01-01T00:00:00Z deterministic


def compute_evidence_chain_hash(evidence_id: str, payload: Dict[str, Any], previous_hash: str = "0") -> str:
    """Deterministic chain_hash for evidence persistence.

    Canonical JSON sort_keys, SHA-256 over evidence_id|previous_hash|payload.
    Repeated identical input => identical hash. Tampering detectable via hash mismatch.
    """
    canonical = json.dumps({"evidence_id": evidence_id, "previous_hash": previous_hash, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class EvidenceChain:
    """Blockchain for tracking evidence provenance."""

    def __init__(self, deterministic: bool = False):
        self.deterministic = deterministic
        self.chain: List[EvidenceBlock] = []
        self.create_genesis_block()

    def create_genesis_block(self) -> EvidenceBlock:
        """Create the first block in the chain."""
        ts = FIXED_TIMESTAMP if self.deterministic else time.time()
        block = EvidenceBlock(
            index=0,
            timestamp=ts,
            evidence_hash='',
            previous_hash='0',
            data={'message': 'Genesis block'},
        )
        self.chain.append(block)
        return block

    def add_block(self, evidence_hash: str, data: Dict[str, Any]) -> EvidenceBlock:
        """Add a new block to the chain."""
        previous_block = self.chain[-1]
        ts = FIXED_TIMESTAMP if self.deterministic else time.time()
        block = EvidenceBlock(
            index=len(self.chain),
            timestamp=ts,
            evidence_hash=evidence_hash,
            previous_hash=previous_block.hash,
            data=data,
        )
        self.chain.append(block)
        return block

    def is_chain_valid(self) -> bool:
        """Validate the entire blockchain."""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            # Check current hash
            if current_block.hash != current_block.compute_hash():
                return False

            # Check linkage
            if current_block.previous_hash != previous_block.hash:
                return False

        return True