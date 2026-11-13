import unittest
from iwfi.chain_integrity import ChainStatus, assess_inclusion, validate_inclusion_observation
BTC="a"*64
ETH="0x"+"b"*64
def obs(oid,network="bitcoin-mainnet",kind="INCLUSION",block_hash=None,**extra):
    return {"observation_id":oid,"network_id":network,"source_id":"node-a","observed_at_utc":"2026-11-13T20:00:00Z","evidence_kind":kind,"block":{"height":100,"hash":block_hash or (BTC if network=="bitcoin-mainnet" else ETH)},**extra}
class ChainIntegrityTests(unittest.TestCase):
    def test_inclusion_alone_is_unresolved(self): self.assertEqual(assess_inclusion([obs("i1")]).status,ChainStatus.CANONICALITY_UNRESOLVED)
    def test_positive_membership(self): self.assertEqual(assess_inclusion([obs("i1",kind="CANONICAL_MEMBERSHIP",evidence_reference="getblockheader")]).status,ChainStatus.INCLUDED)
    def test_noncanonical_proof(self): self.assertEqual(assess_inclusion([obs("i1",kind="NON_CANONICAL_PROOF",evidence_reference="in_active_chain=false")]).status,ChainStatus.NOT_CANONICAL)
    def test_absence_is_not_reversal(self): self.assertEqual(assess_inclusion([]).status,ChainStatus.OBSERVED)
    def test_conflict_is_unresolved(self):
        r=assess_inclusion([obs("p",kind="CANONICAL_MEMBERSHIP",evidence_reference="node-a"),obs("n",kind="NON_CANONICAL_PROOF",evidence_reference="node-b")])
        self.assertEqual(r.status,ChainStatus.CANONICALITY_UNRESOLVED); self.assertEqual(r.conflicting_observation_ids,("n",))
    def test_ethereum_safe(self): self.assertEqual(assess_inclusion([obs("s","eip155:1","ETHEREUM_SAFE_TAG",evidence_reference="eth_getBlockByNumber",tag="safe")]).status,ChainStatus.SAFE)
    def test_ethereum_finalized(self): self.assertEqual(assess_inclusion([obs("f","eip155:1","ETHEREUM_FINALIZED_TAG",evidence_reference="eth_getBlockByNumber",tag="finalized")]).status,ChainStatus.FINALIZED)
    def test_bitcoin_rejects_eth_finality(self):
        with self.assertRaises(ValueError): validate_inclusion_observation(obs("bad",kind="ETHEREUM_FINALIZED_TAG",evidence_reference="rpc",tag="finalized"))
    def test_cannot_combine_different_blocks(self):
        with self.assertRaises(ValueError): assess_inclusion([obs("a"),obs("b",block_hash="c"*64)])
    def test_reinclusion_is_new_observation(self):
        a,b=obs("old"),obs("new",block_hash="c"*64)
        self.assertNotEqual(a["observation_id"],b["observation_id"]); self.assertNotEqual(a["block"]["hash"],b["block"]["hash"])
if __name__=="__main__": unittest.main()
