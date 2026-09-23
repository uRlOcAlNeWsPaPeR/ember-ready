from app.checklist.rules import generate_checklist
from app.schemas import ConstructionType, HouseholdProfile, Ownership


def make_profile(**overrides) -> HouseholdProfile:
    defaults = dict(
        ownership=Ownership.OWN,
        has_pets=False,
        mobility_needs=False,
        construction_type=ConstructionType.OTHER_OR_UNKNOWN,
    )
    defaults.update(overrides)
    return HouseholdProfile(**defaults)


def all_text(items):
    return " ".join(i.text for i in items)


def test_baseline_profile_has_no_incident_specific_language():
    result = generate_checklist(make_profile())
    combined = all_text(result.defensible_space + result.go_bag + result.evacuation_route) + result.note
    # Sanity: never claims to know about a real/active event.
    for banned in ["evacuate now", "mandatory evacuation order has been issued", "the fire is"]:
        assert banned not in combined.lower()
    assert "does not reflect any specific active fire" in result.note


def test_renter_gets_renter_specific_defensible_space_items():
    owner_result = generate_checklist(make_profile(ownership=Ownership.OWN))
    renter_result = generate_checklist(make_profile(ownership=Ownership.RENT))

    owner_reasons = {r for item in owner_result.defensible_space for r in item.reasons}
    renter_reasons = {r for item in renter_result.defensible_space for r in item.reasons}

    assert "homeowner" in owner_reasons
    assert "renter" not in owner_reasons
    assert "renter" in renter_reasons
    assert "homeowner" not in renter_reasons


def test_pet_owner_gets_extra_go_bag_and_evacuation_items():
    no_pets = generate_checklist(make_profile(has_pets=False))
    with_pets = generate_checklist(make_profile(has_pets=True))

    assert len(with_pets.go_bag) > len(no_pets.go_bag)
    assert any("pet_owner" in item.reasons for item in with_pets.go_bag)
    assert any("pet_owner" in item.reasons for item in with_pets.evacuation_route)
    assert not any("pet_owner" in item.reasons for item in no_pets.go_bag)


def test_mobility_needs_adds_registry_and_equipment_items():
    result = generate_checklist(make_profile(mobility_needs=True))
    assert any("mobility_needs" in item.reasons for item in result.go_bag)
    assert any("registry" in item.text.lower() for item in result.evacuation_route)


def test_construction_type_changes_defensible_space_guidance():
    wood = generate_checklist(make_profile(construction_type=ConstructionType.WOOD_SIDING_OR_SHAKE_ROOF))
    masonry = generate_checklist(make_profile(construction_type=ConstructionType.STUCCO_OR_MASONRY))
    mobile = generate_checklist(make_profile(construction_type=ConstructionType.MOBILE_OR_MANUFACTURED))

    assert any("wood siding" in item.text.lower() for item in wood.defensible_space)
    assert any("masonry" in item.text.lower() or "stucco" in item.text.lower() for item in masonry.defensible_space)
    assert any("skirting" in item.text.lower() for item in mobile.defensible_space)


def test_everyone_gets_core_items_regardless_of_profile():
    minimal = generate_checklist(make_profile())
    loaded = generate_checklist(
        make_profile(
            ownership=Ownership.RENT,
            has_pets=True,
            mobility_needs=True,
            construction_type=ConstructionType.MOBILE_OR_MANUFACTURED,
        )
    )
    minimal_core = {i.text for i in minimal.defensible_space if "everyone" in i.reasons}
    loaded_core = {i.text for i in loaded.defensible_space if "everyone" in i.reasons}
    assert minimal_core == loaded_core
    assert len(minimal_core) > 0
