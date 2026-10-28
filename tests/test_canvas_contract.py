import json
import subprocess
from pathlib import Path
import pytest

from video_editor.canvas_contract import canonical_hash, prepare_hub_input


@pytest.fixture
def card():
    return {"id": "story-one", "revision": 2, "digest": "review-digest", "state": "needs_review", "artifact": {"sha256": "a" * 64}}


def prepare(card, **changes):
    values = {"expected_digest": "review-digest", "account_key": "astel.u:instagram", "text": "Согласуемая подпись", "media_url": "https://media.example.test/final.mp4", "available_until": "2030-01-02T00:00:00Z", "scheduled_at": "2030-01-01T00:00:00Z", "allowed_hosts": ["media.example.test"]}
    return prepare_hub_input(card, **{**values, **changes})


def test_handoff_is_only_a_version_bound_simulation(card):
    result = prepare(card)
    assert not result["submitted"]
    assert result["input"]["mode"] == "simulation"
    assert result["input"]["assets"][0]["digest"] == "sha256:" + "a" * 64
    assert prepare(card) == result
    assert prepare(card, text="Different caption")["input_digest"] != result["input_digest"]


@pytest.mark.parametrize("change", [{"expected_digest": "old"}, {"account_key": "other:instagram"}, {"media_url": "file:///private/file.mp4"}, {"media_url": "https://127.0.0.1/file.mp4", "allowed_hosts": ["127.0.0.1"]}, {"available_until": "2029-12-31T00:00:00Z"}, {"scheduled_at": "2030-01-01T00:00:00"}])
def test_stale_or_unusable_delivery_is_rejected(card, change):
    with pytest.raises(ValueError): prepare(card, **change)


def test_superseded_card_cannot_prepare_handoff(card):
    with pytest.raises(ValueError): prepare({**card, "state": "superseded"})


def test_delivery_revision_is_independent_and_strict(card):
    plan=prepare(card,delivery_revision=3)['input']
    assert plan['revision']==3 and plan['assets'][0]['revision']=='2'
    for invalid in [0,False,-1,'3']:
        with pytest.raises(ValueError):prepare(card,delivery_revision=invalid)


def test_exact_existing_hub_contract_accepts_adapter_output(card):
    contract = Path('/Users/oleh/Documents/Codex/2026-10-28/task/radar-acceptance/dist/hub/contract.js')
    if not contract.is_file(): pytest.skip('Existing Hub candidate checkout is not available')
    node = Path('/Users/oleh/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
    # Static module URI from the known local checkout, never a renderer argument.
    script = "import fs from 'node:fs';\nimport {validate,hash} from '" + contract.as_uri() + "';\n" + '''
const plan=JSON.parse(fs.readFileSync(0,'utf8'));
const route={projectId:'copilot',brandId:'astel.u',platform:'instagram',accountKey:'astel.u:instagram',adapter:'mock',executionOwner:'provider',mode:'simulation'};
validate(plan,{id:'offline-fixture',role:'producer',projects:['copilot'],scopes:['submit']},[route],['media.example.test']);
process.stdout.write(hash(plan));
'''
    result = prepare(card)
    proc = subprocess.run([str(node), '--input-type=module', '-e', script], input=json.dumps(result['input'],ensure_ascii=False), text=True, capture_output=True, check=True)
    assert proc.stdout == result['input_digest']
