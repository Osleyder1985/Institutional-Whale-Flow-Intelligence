"""Evidence-first chain inclusion and canonicality assessment for BTC and ETH."""
from __future__ import annotations
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

class ChainStatus(str, Enum):
    OBSERVED="OBSERVED"
    INCLUDED="INCLUDED"
    CANONICALITY_UNRESOLVED="CANONICALITY_UNRESOLVED"
    NOT_CANONICAL="NOT_CANONICAL"
    SAFE="SAFE"
    FINALIZED="FINALIZED"

class EvidenceKind(str, Enum):
    INCLUSION="INCLUSION"
    CANONICAL_MEMBERSHIP="CANONICAL_MEMBERSHIP"
    NON_CANONICAL_PROOF="NON_CANONICAL_PROOF"
    ETHEREUM_SAFE_TAG="ETHEREUM_SAFE_TAG"
    ETHEREUM_FINALIZED_TAG="ETHEREUM_FINALIZED_TAG"

@dataclass(frozen=True)
class ChainAssessment:
    status: ChainStatus
    inclusion_count: int
    supporting_observation_ids: tuple[str,...]
    conflicting_observation_ids: tuple[str,...]
    limitations: tuple[str,...]

def _text(value: Any, field: str) -> str:
    if not isinstance(value,str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value

def validate_inclusion_observation(item: Mapping[str,Any]) -> None:
    network=_text(item.get("network_id"),"network_id")
    _text(item.get("observation_id"),"observation_id")
    _text(item.get("source_id"),"source_id")
    _text(item.get("observed_at_utc"),"observed_at_utc")
    kind=EvidenceKind(_text(item.get("evidence_kind"),"evidence_kind"))
    if network not in {"bitcoin-mainnet","eip155:1"}: raise ValueError("unsupported mainnet network_id")
    block=item.get("block")
    if not isinstance(block,Mapping): raise ValueError("block must be an object")
    height=block.get("height"); block_hash=_text(block.get("hash"),"block.hash")
    if isinstance(height,bool) or not isinstance(height,int) or height<0: raise ValueError("block.height must be non-negative")
    if network=="bitcoin-mainnet":
        if len(block_hash)!=64 or any(c not in "0123456789abcdefABCDEF" for c in block_hash): raise ValueError("invalid Bitcoin block hash")
    elif len(block_hash)!=66 or not block_hash.startswith("0x") or any(c not in "0123456789abcdefABCDEF" for c in block_hash[2:]): raise ValueError("invalid Ethereum block hash")
    if kind in {EvidenceKind.ETHEREUM_SAFE_TAG,EvidenceKind.ETHEREUM_FINALIZED_TAG} and network!="eip155:1": raise ValueError("Ethereum finality evidence cannot be applied to Bitcoin")
    if kind in {EvidenceKind.CANONICAL_MEMBERSHIP,EvidenceKind.NON_CANONICAL_PROOF,EvidenceKind.ETHEREUM_SAFE_TAG,EvidenceKind.ETHEREUM_FINALIZED_TAG}: _text(item.get("evidence_reference"),"evidence_reference")
    if kind==EvidenceKind.ETHEREUM_SAFE_TAG and item.get("tag")!="safe": raise ValueError("safe evidence requires tag='safe'")
    if kind==EvidenceKind.ETHEREUM_FINALIZED_TAG and item.get("tag")!="finalized": raise ValueError("finalized evidence requires tag='finalized'")

def assess_inclusion(observations: Iterable[Mapping[str,Any]]) -> ChainAssessment:
    """Assess one block identity; missing data never proves non-canonicality."""
    items=tuple(observations)
    if not items: return ChainAssessment(ChainStatus.OBSERVED,0,(),(),("No inclusion evidence supplied.",))
    for item in items: validate_inclusion_observation(item)
    identities={(i["network_id"],i["block"]["height"],i["block"]["hash"]) for i in items}
    if len(identities)!=1: raise ValueError("observations must refer to exactly one block identity")
    network=items[0]["network_id"]; inclusion=[]; positive=[]; negative=[]; safe=[]; finalized=[]
    for item in items:
        kind=EvidenceKind(item["evidence_kind"]); oid=item["observation_id"]
        if kind==EvidenceKind.INCLUSION: inclusion.append(oid)
        elif kind==EvidenceKind.CANONICAL_MEMBERSHIP: positive.append(oid)
        elif kind==EvidenceKind.NON_CANONICAL_PROOF: negative.append(oid)
        elif kind==EvidenceKind.ETHEREUM_SAFE_TAG: positive.append(oid); safe.append(oid)
        elif kind==EvidenceKind.ETHEREUM_FINALIZED_TAG: positive.append(oid); safe.append(oid); finalized.append(oid)
    if positive and negative:
        return ChainAssessment(ChainStatus.CANONICALITY_UNRESOLVED,len(inclusion),tuple(sorted(set(positive))),tuple(sorted(set(negative))),("Sources conflict on canonicality.",))
    if negative:
        return ChainAssessment(ChainStatus.NOT_CANONICAL,len(inclusion),(),tuple(sorted(set(negative))),("This block inclusion is non-canonical; transaction reversal is not established.",))
    if finalized: status=ChainStatus.FINALIZED
    elif safe: status=ChainStatus.SAFE
    elif positive: status=ChainStatus.INCLUDED
    elif inclusion: status=ChainStatus.CANONICALITY_UNRESOLVED
    else: status=ChainStatus.OBSERVED
    limits=[]
    if network=="bitcoin-mainnet" and status==ChainStatus.INCLUDED: limits.append("Bitcoin inclusion is evidenced; no protocol-finality claim is made.")
    if status in {ChainStatus.OBSERVED,ChainStatus.CANONICALITY_UNRESOLVED}: limits.append("No positive canonicality conclusion is justified.")
    if safe or finalized: limits.append("Ethereum safe/finalized status is the reporting node's view at observed_at_utc.")
    return ChainAssessment(status,len(inclusion),tuple(sorted(set(positive))),(),tuple(limits))
