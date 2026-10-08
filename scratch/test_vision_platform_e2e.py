import os
import sys

# Ensure backend directory is in sys.path
backend_dir = r"d:\lab-foh-enterprise-dev\backend"
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from app.main import app
from app.core.deps import get_current_user
from app.models.user import User

mock_admin = User(
    id="test_admin_id",
    name="Test Admin",
    email="admin@test.com",
    password_hash="fakehash",
    role="OWNER",
    is_active=True,
    status="ACTIVE",
    tenant_id="org_default"
)
app.dependency_overrides[get_current_user] = lambda: mock_admin

client = TestClient(app)

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_vision_platform():
    log("=== Commencing Production-Grade Vision Platform In-Process E2E Test ===")
    
    # 1. Check health / active models
    r = client.get("/vision/models")
    assert r.status_code == 200, f"GET /vision/models failed: {r.text}"
    models = r.json()
    log(f"Found {len(models)} registered models in catalog.")
    for m in models:
        log(f"  - Model: {m['model_name']} (id: {m['id']}, status: {m['status']}, active: {m['is_active']})")

    # 2. Check unregistered candidate files
    r = client.get("/vision/models/unregistered")
    assert r.status_code == 200, f"GET /vision/models/unregistered failed: {r.text}"
    unregistered = r.json()
    log(f"Found {len(unregistered)} unregistered weights in candidates directory.")

    # Find the candidate model we registered or register one
    candidate = next((m for m in models if m["status"] == "CANDIDATE"), None)
    if not candidate:
        if unregistered:
            target_unreg = unregistered[0]
            log(f"Registering candidate weights: {target_unreg['filename']}")
            reg_payload = {
                "model_name": "candidate_restaurant_v1",
                "file_path": target_unreg["path"],
                "version": "1.0.0",
                "architecture": "YOLO11",
                "task": "detect",
                "class_map": {"60": "dining_table"}
            }
            r = client.post("/vision/models/register", json=reg_payload)
            assert r.status_code == 200, f"Register failed: {r.text}"
            candidate = r.json()
            log(f"Registered candidate model ID: {candidate['id']}")
        else:
            log("No unregistered candidates found, using existing candidate if available.")

    if candidate:
        cid = candidate["id"]
        log(f"\n--- Testing 3-Tier Validation on Candidate ID: {cid} ---")
        r = client.post(f"/vision/models/{cid}/validate")
        assert r.status_code == 200, f"Validation failed: {r.text}"
        val_res = r.json()
        log(f"Validation Result: {val_res.get('overall_status')}")
        log(f"  Tier 1 Structural: {val_res.get('tier1_structural', {}).get('status')}")
        log(f"  Tier 2 Smoke Test: {val_res.get('tier2_smoke_test', {}).get('status')}")
        log(f"  Tier 3 Ontology:   {val_res.get('tier3_ontology', {}).get('status')}")
        assert val_res.get("overall_status") == "PASSED", f"Expected PASSED, got {val_res}"

        log(f"\n--- Testing Comparative Offline Benchmark & 500-Frame Stability ---")
        bench_payload = {
            "sample_frames": 25,
            "run_500_frame_test": True
        }
        r = client.post(f"/vision/models/{cid}/benchmark", json=bench_payload)
        assert r.status_code == 200, f"Benchmark failed: {r.text}"
        bench_res = r.json()
        cand_metrics = bench_res.get("candidate_metrics", {})
        summary = bench_res.get("comparison_summary", {})
        log(f"Candidate FPS: {cand_metrics.get('fps')} | Avg Latency: {cand_metrics.get('avg_latency_ms')}ms")
        log(f"Candidate Stability Score: {cand_metrics.get('spatial_stability_score')}")
        log(f"Recommendation: {summary.get('recommendation')}")

        log(f"\n--- Testing Dark-Launch Shadow Concurrent Evaluation ---")
        r = client.post(f"/vision/models/{cid}/shadow/start?camera_id=cam_main")
        assert r.status_code == 200, f"Shadow start failed: {r.text}"
        log("Shadow evaluation started.")

        # Check status
        r = client.get("/vision/models/shadow/status")
        assert r.status_code == 200, f"Shadow status failed: {r.text}"
        status_res = r.json()
        log(f"Shadow status: Active={status_res.get('active')}, Model={status_res.get('model_id')}")

        # Stop shadow
        r = client.post(f"/vision/models/{cid}/shadow/stop?camera_id=cam_main")
        assert r.status_code == 200, f"Shadow stop failed: {r.text}"
        log("Shadow evaluation stopped cleanly.")

        # Atomic Activation & Rollback Test
        if candidate.get("status") == "CANDIDATE":
            log(f"\n--- Testing Atomic Hot-Swap Activation for Candidate {cid} ---")
            r = client.post(f"/vision/models/{cid}/activate", json={"reason": "Automated E2E pipeline verification"})
            assert r.status_code == 200, f"Activation failed: {r.text}"
            log(f"Successfully activated model {cid} into PRODUCTION!")

            # Verify catalogue reflects new production model
            r = client.get("/vision/models")
            current_active = next((m for m in r.json() if m["is_active"]), None)
            log(f"Currently active production model: {current_active['model_name']} (ID: {current_active['id']})")
            assert current_active["id"] == cid, "Active model ID does not match promoted candidate!"

            # Test Safe Instant Rollback
            log(f"\n--- Testing Safe Instant Rollback with Audit Reason ---")
            r = client.post("/vision/models/rollback", json={"reason": "Rollback test in E2E verification"})
            assert r.status_code == 200, f"Rollback failed: {r.text}"
            rolled_back_model = r.json()
            log(f"Rolled back to previous model: {rolled_back_model['model_name']} (ID: {rolled_back_model['id']})")

    # Verify FOH integrity (Existing endpoints)
    log(f"\n--- Verifying Core FOH Application State Integrity ---")
    r = client.get("/floor-plans")
    assert r.status_code == 200, f"Floor plans failed: {r.text}"
    log(f"Floor plans endpoint returned HTTP 200 (Count: {len(r.json())})")

    r = client.get("/tables")
    assert r.status_code == 200, f"Tables endpoint failed: {r.text}"
    log(f"Tables endpoint returned HTTP 200 (Count: {len(r.json())})")

    log("\n🎉 ALL E2E VISION PLATFORM & FOH INTEGRITY TESTS PASSED!", "SUCCESS")

if __name__ == "__main__":
    test_vision_platform()
