"""Full Actor Registry v1.2 freeze and offline reconstruction manifest v1.1."""
import hashlib
import json
from datetime import datetime

from iwfi.evidence_snapshot_provenance import verify_snapshot_payload

_CANON = "IWFI-JSON-C14N-1"
_ALLOWED_REF_TYPES = {"SOURCE_OBSERVATION", "ATTRIBUTION_CLAIM"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _time(value):
    if not isinstance(value, str) or len(value) != 20 or not value.endswith("Z"):
        raise ValueError("UTC timestamp must use YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("invalid UTC timestamp") from exc


def _collect_registry_references(registry):
    if not isinstance(registry, dict) or registry.get("contract_version") != "1.2.0":
        raise ValueError("Actor Registry contract_version 1.2.0 is required")
    found = []
    def add(container, path, polarity):
        refs = container.get(polarity, [])
        if not isinstance(refs, list):
            raise ValueError(path + "." + polarity + " must be an array")
        for ref in refs:
            if not isinstance(ref, dict) or set(ref) != {"ref_type", "ref_id"}:
                raise ValueError(path + "." + polarity + " contains invalid typed reference")
            ref_type, ref_id = ref.get("ref_type"), ref.get("ref_id")
            if ref_type not in _ALLOWED_REF_TYPES or not isinstance(ref_id, str) or not ref_id.strip():
                raise ValueError(path + "." + polarity + " contains unsupported reference")
            found.append({"record_path": path, "polarity": polarity,
                          "ref_type": ref_type, "ref_id": ref_id})
    actors = registry.get("actors")
    relationships = registry.get("relationships")
    if not isinstance(actors, list) or not isinstance(relationships, list):
        raise ValueError("actors and relationships must be arrays")
    actor_ids, relationship_ids = set(), set()
    for i, actor in enumerate(actors):
        if not isinstance(actor, dict) or not isinstance(actor.get("actor_id"), str):
            raise ValueError("invalid actor record")
        if actor["actor_id"] in actor_ids:
            raise ValueError("duplicate actor_id")
        actor_ids.add(actor["actor_id"])
        base = "actors/" + actor["actor_id"]
        add(actor, base, "evidence_refs")
        add(actor, base, "counter_evidence_refs")
        for field in ("aliases", "classifications"):
            entries = actor.get(field, [])
            if not isinstance(entries, list):
                raise ValueError(base + "/" + field + " must be an array")
            for j, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    raise ValueError("invalid " + field + " entry")
                if field == "aliases":
                    identity = entry.get("value")
                else:
                    identity = entry.get("classification")
                if not isinstance(identity, str) or not identity.strip():
                    raise ValueError(field + " entry requires stable value/classification")
                path = base + "/" + field + "/" + identity
                add(entry, path, "evidence_refs")
    for relationship in relationships:
        if not isinstance(relationship, dict) or not isinstance(relationship.get("relationship_id"), str):
            raise ValueError("invalid relationship record")
        rid = relationship["relationship_id"]
        if rid in relationship_ids:
            raise ValueError("duplicate relationship_id")
        relationship_ids.add(rid)
        path = "relationships/" + rid
        add(relationship, path, "evidence_refs")
        add(relationship, path, "counter_evidence_refs")
    found.sort(key=lambda x: (x["record_path"], x["polarity"], x["ref_type"], x["ref_id"]))
    identities = [(x["record_path"], x["polarity"], x["ref_type"], x["ref_id"]) for x in found]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate evidence reference within the same registry field")
    return found


def _reference_key(ref_type, ref_id):
    return ref_type + ":" + ref_id


def build_actor_registry_reconstruction_manifest_v1_1(
    *, actor_registry, snapshot_descriptors, reference_snapshot_map,
    knowledge_cutoff_utc, valid_time_utc, algorithm_id, algorithm_version,
    parameters, root_claim_id, root_claim_hash, root_claim_contract_version,
):
    """Freeze entire registry plus every supporting/counter reference and snapshot."""
    if not isinstance(actor_registry, dict):
        raise ValueError("actor_registry must be an object")
    cutoff, valid = _time(knowledge_cutoff_utc), _time(valid_time_utc)
    if not all(isinstance(x, str) and x.strip() for x in
               (algorithm_id, algorithm_version, root_claim_id, root_claim_contract_version)):
        raise ValueError("algorithm and root claim identifiers/versions are required")
    if not isinstance(root_claim_hash, str) or len(root_claim_hash) != 64:
        raise ValueError("root_claim_hash must be SHA-256 hex")
    try:
        int(root_claim_hash, 16)
    except ValueError as exc:
        raise ValueError("root_claim_hash must be SHA-256 hex") from exc
    if not isinstance(parameters, dict) or not isinstance(reference_snapshot_map, dict):
        raise ValueError("parameters and reference_snapshot_map must be objects")
    refs = _collect_registry_references(actor_registry)
    descriptors = {}
    for descriptor in snapshot_descriptors:
        sid = descriptor.get("source_snapshot_id") if isinstance(descriptor, dict) else None
        if not isinstance(sid, str) or not sid.strip() or sid in descriptors:
            raise ValueError("snapshot IDs must be present and unique")
        if _time(descriptor.get("retrieved_at_utc")) > cutoff:
            raise ValueError("snapshot retrieved after knowledge cutoff")
        descriptors[sid] = descriptor
    expected_keys = {_reference_key(r["ref_type"], r["ref_id"]) for r in refs}
    if set(reference_snapshot_map) != expected_keys:
        raise ValueError("snapshot map must cover exactly every unique typed registry reference")
    mapped = {}
    dependencies = {}
    for ref in refs:
        key = _reference_key(ref["ref_type"], ref["ref_id"])
        ids = reference_snapshot_map[key]
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, list) or not ids or any(sid not in descriptors for sid in ids):
            raise ValueError("every registry reference needs known snapshot dependencies: " + key)
        mapped[(ref["record_path"], ref["polarity"], ref["ref_type"], ref["ref_id"])] = sorted(set(ids))
        for sid in ids:
            dependencies[sid] = descriptors[sid]
    frozen_refs = []
    for ref in refs:
        key = (ref["record_path"], ref["polarity"], ref["ref_type"], ref["ref_id"])
        frozen_refs.append({**ref, "snapshot_ids": mapped[key]})
    frozen_dependencies = []
    for sid, descriptor in sorted(dependencies.items()):
        frozen_dependencies.append({
            "source_id": descriptor.get("source_id"),
            "source_snapshot_id": sid,
            "retrieved_at_utc": descriptor.get("retrieved_at_utc"),
            "payload_hash": descriptor.get("payload_hash"),
            "hash_algorithm": descriptor.get("hash_algorithm"),
            "hash_scope": descriptor.get("hash_scope"),
            "canonicalization_version": descriptor.get("canonicalization_version"),
        })
    manifest = {
        "manifest_version": "1.1.0",
        "root_claim_id": root_claim_id,
        "root_claim_contract_version": root_claim_contract_version,
        "root_claim_hash": root_claim_hash,
        "actor_registry_contract_version": actor_registry["contract_version"],
        "actor_registry_hash": _hash(_canonical(actor_registry)),
        "actor_registry_hash_algorithm": "SHA-256",
        "actor_registry_canonicalization_version": _CANON,
        "knowledge_cutoff_utc": knowledge_cutoff_utc,
        "valid_time_utc": valid_time_utc,
        "algorithm_id": algorithm_id,
        "algorithm_version": algorithm_version,
        "parameters": parameters,
        "references": frozen_refs,
        "dependencies": frozen_dependencies,
        "manifest_hash_algorithm": "SHA-256",
        "manifest_canonicalization_version": _CANON,
    }
    manifest["manifest_hash"] = _hash(_canonical(manifest))
    return manifest


def verify_actor_registry_reconstruction_manifest_v1_1(
    *, manifest, actor_registry, snapshots_by_id, payloads_by_id,
    knowledge_cutoff_utc, valid_time_utc,
):
    """Fail-closed verifier for registry bytes, reference completeness and snapshots."""
    def fail(reason, details=None):
        return {"status": "INTEGRITY_FAILED", "reason": reason, "dependencies": details or []}
    if not all(isinstance(x, dict) for x in (manifest, actor_registry, snapshots_by_id, payloads_by_id)):
        return {"status": "INVALID_INPUT", "reason": "OBJECTS_REQUIRED", "dependencies": []}
    try:
        if manifest.get("manifest_canonicalization_version") != _CANON:
            return fail("UNSUPPORTED_CANONICALIZATION")
        unsigned = {k: v for k, v in manifest.items() if k != "manifest_hash"}
        if manifest.get("manifest_hash") != _hash(_canonical(unsigned)):
            return fail("MANIFEST_HASH_MISMATCH")
        if manifest.get("actor_registry_contract_version") != actor_registry.get("contract_version"):
            return fail("REGISTRY_CONTRACT_VERSION_MISMATCH")
        if manifest.get("actor_registry_hash") != _hash(_canonical(actor_registry)):
            return fail("ACTOR_REGISTRY_HASH_MISMATCH")
        if manifest.get("root_claim_id") is None or manifest.get("root_claim_hash") is None:
            return fail("ROOT_CLAIM_BINDING_MISSING")
        cutoff, valid = _time(knowledge_cutoff_utc), _time(valid_time_utc)
        if manifest.get("knowledge_cutoff_utc") != knowledge_cutoff_utc:
            return fail("KNOWLEDGE_CUTOFF_MISMATCH")
        if manifest.get("valid_time_utc") != valid_time_utc:
            return fail("VALID_TIME_MISMATCH")
        refs = _collect_registry_references(actor_registry)
    except (KeyError, TypeError, ValueError):
        return fail("INVALID_CANONICAL_OR_REGISTRY_INPUT")
    expected = {(r["record_path"], r["polarity"], r["ref_type"], r["ref_id"]) for r in refs}
    frozen = manifest.get("references")
    if not isinstance(frozen, list):
        return fail("REFERENCES_NOT_ARRAY")
    actual = set()
    reference_snapshot_ids = set()
    for item in frozen:
        if not isinstance(item, dict):
            return fail("INVALID_REFERENCE_ENTRY")
        identity = (item.get("record_path"), item.get("polarity"), item.get("ref_type"), item.get("ref_id"))
        if identity in actual:
            return fail("DUPLICATE_REFERENCE_ENTRY")
        actual.add(identity)
        ids = item.get("snapshot_ids")
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            return fail("INVALID_REFERENCE_SNAPSHOT_MAPPING")
        reference_snapshot_ids.update(ids)
    if actual != expected:
        return fail("REGISTRY_REFERENCE_SET_MISMATCH")
    deps = manifest.get("dependencies")
    if not isinstance(deps, list):
        return fail("DEPENDENCIES_NOT_ARRAY")
    dep_by_id = {}
    for dep in deps:
        if not isinstance(dep, dict):
            return fail("INVALID_DEPENDENCY")
        sid = dep.get("source_snapshot_id")
        if not isinstance(sid, str) or sid in dep_by_id:
            return fail("DUPLICATE_OR_INVALID_DEPENDENCY")
        dep_by_id[sid] = dep
    if set(dep_by_id) != reference_snapshot_ids:
        return fail("DEPENDENCY_REFERENCE_SET_MISMATCH")
    results = []
    for sid, dep in sorted(dep_by_id.items()):
        snapshot, payload = snapshots_by_id.get(sid), payloads_by_id.get(sid)
        if not isinstance(snapshot, dict):
            results.append({"source_snapshot_id": sid, "status": "SNAPSHOT_MISSING"})
            continue
        if not isinstance(payload, bytes):
            results.append({"source_snapshot_id": sid, "status": "PAYLOAD_UNAVAILABLE"})
            continue
        fields = ("source_id", "source_snapshot_id", "retrieved_at_utc", "payload_hash",
                  "hash_algorithm", "hash_scope", "canonicalization_version")
        if any(snapshot.get(k) != dep.get(k) for k in fields):
            status = "SNAPSHOT_DESCRIPTOR_MISMATCH"
        else:
            try:
                if _time(snapshot.get("retrieved_at_utc")) > cutoff:
                    status = "SNAPSHOT_AFTER_CUTOFF"
                else:
                    status = verify_snapshot_payload(snapshot, payload).get("status")
            except ValueError:
                status = "INVALID_SNAPSHOT_TIMESTAMP"
        results.append({"source_snapshot_id": sid, "status": status})
    if any(x["status"] != "HASH_VERIFIED" for x in results):
        return fail("SNAPSHOT_VERIFICATION_FAILED", results)
    return {"status": "ACTOR_REGISTRY_RECONSTRUCTION_VERIFIED",
            "registry_hash_status": "HASH_VERIFIED",
            "reference_status": "COMPLETE_EXACT_MATCH",
            "root_claim_id": manifest["root_claim_id"],
            "knowledge_cutoff_utc": knowledge_cutoff_utc,
            "valid_time_utc": valid_time_utc,
            "dependencies": results}
