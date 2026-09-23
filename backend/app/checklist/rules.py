"""Rule-based (not ML) personalized preparedness checklist.

Every item is general, area-independent preparedness guidance — never
incident-specific evacuation instructions. Each item records which inputs
triggered it (`reasons`), so the API/UI can show *why* a recommendation
appeared, matching the transparency approach used in the risk scorer.
"""
from __future__ import annotations

from app.schemas import ChecklistItem, ChecklistResult, ConstructionType, HouseholdProfile, Ownership

NOTE = (
    "This checklist is general, area-independent preparedness guidance. It does not reflect "
    "any specific active fire, evacuation order, or incident. For real-time evacuation orders "
    "and incident information, always follow instructions from local fire authorities and "
    "official sources such as Watch Duty."
)


def _item(text: str, *reasons: str) -> ChecklistItem:
    return ChecklistItem(text=text, reasons=list(reasons))


def _defensible_space(profile: HouseholdProfile) -> list[ChecklistItem]:
    items = [
        _item(
            "Clear dead leaves, needles, and debris from the roof, gutters, and the ground "
            "within 5 feet of the home (the 'ember-resistant zone').",
            "everyone",
        ),
        _item(
            "Keep the area within 5 feet of the home free of mulch, dry vegetation, and stored "
            "flammable items such as firewood piles.",
            "everyone",
        ),
        _item(
            "Trim tree branches so they don't overhang the roof or come within 10 feet of the chimney.",
            "everyone",
        ),
        _item(
            "Mow dry grass and remove dead plants within 30 feet of the home.",
            "everyone",
        ),
        _item(
            "Space out shrubs and trees between 30-100 feet from the home to reduce continuous fuel.",
            "everyone",
        ),
    ]

    if profile.ownership == Ownership.OWN:
        items.append(
            _item(
                "Consider ember-resistant vent screens (1/8-inch metal mesh) on attic and "
                "foundation vents.",
                "homeowner",
            )
        )
        items.append(
            _item(
                "If replacing your roof or siding, consider Class A fire-rated roofing and "
                "non-combustible siding materials.",
                "homeowner",
            )
        )
    else:
        items.append(
            _item(
                "Ask your landlord or property manager about clearing dead vegetation/debris "
                "from the property and installing ember-resistant vent screens.",
                "renter",
            )
        )
        items.append(
            _item(
                "Report accumulated dry brush or debris on the property to your landlord or "
                "local code enforcement.",
                "renter",
            )
        )

    if profile.construction_type == ConstructionType.WOOD_SIDING_OR_SHAKE_ROOF:
        items.append(
            _item(
                "Wood siding and shake roofing are more vulnerable to ember ignition — "
                "prioritize maintaining the 5-foot ember-resistant zone around the home.",
                "construction:wood_siding_or_shake_roof",
            )
        )
    elif profile.construction_type == ConstructionType.STUCCO_OR_MASONRY:
        items.append(
            _item(
                "Masonry/stucco exteriors resist embers relatively well, but still check vents, "
                "eaves, and window screens for gaps embers could enter through.",
                "construction:stucco_or_masonry",
            )
        )
    elif profile.construction_type == ConstructionType.MOBILE_OR_MANUFACTURED:
        items.append(
            _item(
                "Manufactured/mobile homes can be vulnerable to ignition underneath — keep "
                "skirting intact and the area underneath clear of debris and storage.",
                "construction:mobile_or_manufactured",
            )
        )

    return items


def _go_bag(profile: HouseholdProfile) -> list[ChecklistItem]:
    items = [
        _item("Water and non-perishable food for several days per person.", "everyone"),
        _item("A copy of important documents (ID, insurance, medical records) in a waterproof pouch.", "everyone"),
        _item("Prescription medications and a basic first aid kit.", "everyone"),
        _item("A flashlight, portable phone charger/battery bank, and a battery-powered radio.", "everyone"),
        _item("A change of clothes and sturdy shoes for each household member.", "everyone"),
        _item("N95 or better masks to protect against wildfire smoke.", "everyone"),
        _item("Cash in small denominations, in case card payments aren't available.", "everyone"),
    ]

    if profile.has_pets:
        items.append(
            _item(
                "Pet food, water, medications, and a leash/carrier for each pet.",
                "pet_owner",
            )
        )
        items.append(
            _item(
                "Vaccination records and a recent photo of each pet, in case you're separated.",
                "pet_owner",
            )
        )
        items.append(
            _item(
                "A list of pet-friendly lodging or shelters in areas outside your immediate region.",
                "pet_owner",
            )
        )

    if profile.mobility_needs:
        items.append(
            _item(
                "A portable charger for powered mobility equipment (wheelchairs, scooters), "
                "plus any spare parts or manual backup equipment.",
                "mobility_needs",
            )
        )
        items.append(
            _item(
                "Extra prescription medications and copies of prescriptions for mobility- or "
                "health-related equipment.",
                "mobility_needs",
            )
        )

    return items


def _evacuation_route(profile: HouseholdProfile) -> list[ChecklistItem]:
    items = [
        _item(
            "Identify at least two different routes out of your neighborhood in case one is blocked.",
            "everyone",
        ),
        _item(
            "Learn your community's evacuation zone or wildfire alert designation, and sign up "
            "for local emergency alert notifications.",
            "everyone",
        ),
        _item(
            "Practice your evacuation route with your household, including pets, at least once.",
            "everyone",
        ),
        _item(
            "Keep your vehicle's fuel tank at least half full during high fire-risk seasons.",
            "everyone",
        ),
        _item(
            "Agree on an out-of-area meeting point and an out-of-area contact person in case "
            "household members are separated.",
            "everyone",
        ),
    ]

    if profile.mobility_needs:
        items.append(
            _item(
                "Register in advance with your local emergency management office's registry "
                "for residents who may need evacuation assistance.",
                "mobility_needs",
            )
        )
        items.append(
            _item(
                "Identify at least one person who can help you evacuate and check on you "
                "during an emergency.",
                "mobility_needs",
            )
        )

    if profile.has_pets:
        items.append(
            _item(
                "Plan ahead for transporting all pets — many public shelters restrict animals, "
                "so know your pet-friendly options before you need them.",
                "pet_owner",
            )
        )

    return items


def generate_checklist(profile: HouseholdProfile) -> ChecklistResult:
    return ChecklistResult(
        defensible_space=_defensible_space(profile),
        go_bag=_go_bag(profile),
        evacuation_route=_evacuation_route(profile),
        note=NOTE,
    )
