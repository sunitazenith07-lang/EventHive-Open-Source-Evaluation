"""110-case visible EventHive contract. Untouched starter intentionally has 24 failures."""
import json
from copy import deepcopy
import pytest
import service as service
from models import RECORD_CLASS, FIELD_NAMES, VALID_STATUSES, VALID_CATEGORIES
from service import load_records, save_records, find_record, search_records, filter_records, update_status, summary, register_attendee
from fixtures import make_records

STATUS_CHECKS = ["Published", "Draft", "Cancelled"]
CATEGORY_CHECKS = ["Workshop", "Talk", "Competition", "Networking"]
SEARCH_CASES = [("AI Workshop", [1]), ("Open Day", [2]), ("Hackathon", [3]), ("Career Talk", [4]), ("Alumni Meetup", [5]), ("Pitch Night", [6]), ("Innovation Hall", [1,6]), ("Main Lawn", [2])]
NORMALIZATION_CASES = [("ai workshop", [1]), ("AI WORKSHOP", [1]), (" AI Workshop ", [1]), ("WORKSHOP", [1]), ("INNOVATION HALL", [1,6]), ("career talk", [4]), ("Pitch Night  ", [6]), (" networking ", [2,5])]

@pytest.mark.parametrize("field", FIELD_NAMES)
def test_model_serialisation_preserves_each_field(field):
    item = make_records()[0]
    assert item.to_dict()[field] == getattr(item, field)

@pytest.mark.parametrize("status", STATUS_CHECKS)
def test_supported_status_values_are_declared(status):
    assert status in VALID_STATUSES

@pytest.mark.parametrize("category", CATEGORY_CHECKS)
def test_supported_categories_are_declared(category):
    assert category in VALID_CATEGORIES

@pytest.mark.parametrize("size", [1,2,4,6])
def test_storage_round_trip(tmp_path, size):
    path = tmp_path / "nested" / "records.json"
    expected = make_records()[:size]
    save_records(expected, path)
    assert [x.to_dict() for x in load_records(path)] == [x.to_dict() for x in expected]

def test_missing_storage_returns_empty_list(tmp_path):
    assert load_records(tmp_path / "missing.json") == []

def test_malformed_json_is_reported(tmp_path):
    path=tmp_path / "broken.json"; path.write_text("[broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError): load_records(path)

def test_non_list_json_is_rejected(tmp_path):
    path=tmp_path / "bad.json"; path.write_text('{"not":"a list"}', encoding="utf-8")
    with pytest.raises(ValueError): load_records(path)

@pytest.mark.parametrize("record_id,expected", [(1,1),(2,2),(3,3),(6,6),(999,None)])
def test_find_record_by_id(record_id, expected):
    found=find_record(make_records(), record_id)
    assert (found.id if found else None) == expected

@pytest.mark.parametrize("category", CATEGORY_CHECKS)
def test_filter_by_each_category(category):
    result=filter_records(make_records(), category=category)
    assert [x.id for x in result] == [x.id for x in make_records() if x.category == category]

@pytest.mark.parametrize("status", STATUS_CHECKS)
def test_filter_by_each_status(status):
    result=filter_records(make_records(), status=status)
    assert [x.id for x in result] == [x.id for x in make_records() if x.status == status]

@pytest.mark.parametrize("category,status", [("Workshop","Published"),("Networking","Draft"),("Competition","Cancelled"),("Talk","Published"),("Workshop","Cancelled"),("Networking","Published")])
def test_combined_filters_return_intersection(category, status):
    result=filter_records(make_records(), category=category, status=status)
    assert [x.id for x in result] == [x.id for x in make_records() if x.category == category and x.status == status]

@pytest.mark.parametrize("query,expected", SEARCH_CASES)
def test_exact_case_search(query, expected):
    assert [x.id for x in search_records(query, make_records())] == expected

@pytest.mark.parametrize("query,expected_count", [("",6),(None,6)])
def test_empty_search_returns_all_records(query, expected_count):
    assert len(search_records(query, make_records())) == expected_count

@pytest.mark.parametrize("status", ["Published","Draft","Cancelled","Published"])
def test_update_status_mutates_explicit_list(status):
    items=make_records(); result=update_status(1, status, items)
    assert result.status == status and items[0].status == status

@pytest.mark.parametrize("status", ["NOT-VALID","","UNKNOWN-STATE"])
def test_invalid_status_update_is_rejected(status):
    with pytest.raises(ValueError): update_status(1, status, make_records())

def test_update_missing_record_is_rejected():
    with pytest.raises(LookupError): update_status(999, "Published", make_records())

@pytest.mark.parametrize("status", STATUS_CHECKS)
def test_summary_status_buckets_are_correct(status):
    items=make_records()
    assert summary(items)["by_status"][status] == sum(x.status == status for x in items)

@pytest.mark.parametrize("category", CATEGORY_CHECKS)
def test_summary_category_buckets_are_correct(category):
    items=make_records()
    assert summary(items)["by_category"][category] == sum(x.category == category for x in items)

def test_summary_empty_catalogue():
    result=summary([])
    assert result["total"] == 0 and result["by_category"] == {}
    assert result["by_status"] == {status:0 for status in VALID_STATUSES}

def test_summary_does_not_mutate_inputs():
    items=make_records(); before=[x.to_dict() for x in items]; summary(items)
    assert [x.to_dict() for x in items] == before

@pytest.mark.parametrize("repeat", [1,2,3,4])
def test_domain_action_happy_path(repeat):
    items=make_records(); count=items[0].registered_count
    register_attendee(1, "new@example.org", items)
    assert items[0].registered_count == count+1 and "new@example.org" in items[0].attendees

@pytest.mark.parametrize("case", [0,1,2,3])
def test_filtering_does_not_mutate_input(case):
    items=make_records(); before=[x.to_dict() for x in items]
    if case==0: filter_records(items, category=CATEGORY_CHECKS[0])
    elif case==1: filter_records(items, status=STATUS_CHECKS[0])
    elif case==2: filter_records(items, query=SEARCH_CASES[0][0])
    else: filter_records(items, category=CATEGORY_CHECKS[2], status=STATUS_CHECKS[1])
    assert [x.to_dict() for x in items] == before

@pytest.mark.parametrize("size", [2,4,6])
def test_sample_subsets_have_unique_ids(size):
    ids=[x.id for x in make_records()[:size]]
    assert len(ids)==len(set(ids))

def test_separate_storage_loads_return_distinct_objects(tmp_path):
    path=tmp_path / "records.json"; save_records(make_records(), path)
    one,two=load_records(path),load_records(path)
    assert one[0] == two[0] and one[0] is not two[0]

@pytest.mark.parametrize("case", [0,1])
def test_repeated_search_is_stable(case):
    items=make_records(); before=[x.to_dict() for x in items]; q=SEARCH_CASES[case][0]
    filter_records(items, query=q); filter_records(items, query=q)
    assert [x.to_dict() for x in items] == before

@pytest.mark.parametrize("query", ["NOT-A-REAL-RECORD-991","xxxxxxxxxx","987654321"])
def test_no_match_query_returns_empty_list(query):
    assert search_records(query, make_records()) == []

# 24 intentional failures on the untouched starter.
@pytest.mark.parametrize("query,expected", NORMALIZATION_CASES)
def test_search_normalises_case_and_whitespace(query, expected):
    assert [x.id for x in search_records(query, make_records())] == expected

@pytest.mark.parametrize("new_status", ["Published","Draft","Cancelled","Published"])
def test_status_update_is_persisted(monkeypatch, new_status):
    items=make_records(); saved=[]
    monkeypatch.setattr(service, "load_records", lambda: items)
    monkeypatch.setattr(service, "save_records", lambda rows, path=service.DATA_FILE: saved.append([x.to_dict() for x in rows]))
    service.update_status(1, new_status)
    assert len(saved)==1 and saved[0][0]["status"]==new_status

@pytest.mark.parametrize("case", [0,1,2,3])
def test_summary_total_includes_cancelled_events(case):
    items=make_records(); terminal=next(x for x in items if x.status=="Cancelled")
    other=[x for x in items if x.status!="Cancelled"]
    selected=[terminal]+other[:case]
    assert summary(selected)["total"] == len(selected)

@pytest.mark.parametrize("invalid_case", ["duplicate-id","invalid-status","invalid-category","negative-id"])
def test_storage_rejects_invalid_records(tmp_path, invalid_case):
    row=make_records()[0].to_dict()
    if invalid_case=="duplicate-id": payload=[row,deepcopy(row)]
    else:
        bad=deepcopy(row)
        if invalid_case=="invalid-status": bad["status"]="Not A Status"
        elif invalid_case=="invalid-category": bad["category"]="Not A Category"
        else: bad["id"]=-1
        payload=[bad]
    path=tmp_path / "invalid.json"; path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError): load_records(path)

@pytest.mark.parametrize("case", [0,1,2,3])
def test_registration_rejects_unsafe_edge_cases(case):
    items=make_records()
    if case==0: items[0].registered_count=items[0].capacity
    elif case==1: items[0].status="Cancelled"
    elif case==2: items[0].attendees.append("duplicate@example.org")
    email="duplicate@example.org" if case==2 else ("   " if case==3 else "new@example.org")
    with pytest.raises(ValueError): register_attendee(1, email, records=items)
