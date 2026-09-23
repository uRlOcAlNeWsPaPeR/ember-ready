from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.checklist.rules import generate_checklist
from app.schemas import ConstructionType, HouseholdProfile, Ownership

router = APIRouter()


class HouseholdProfileIn(BaseModel):
    ownership: Ownership
    has_pets: bool
    mobility_needs: bool
    construction_type: ConstructionType = ConstructionType.OTHER_OR_UNKNOWN


class ChecklistItemOut(BaseModel):
    text: str
    reasons: list[str]


class ChecklistResponse(BaseModel):
    defensible_space: list[ChecklistItemOut]
    go_bag: list[ChecklistItemOut]
    evacuation_route: list[ChecklistItemOut]
    note: str


@router.post("/checklist", response_model=ChecklistResponse)
def post_checklist(profile: HouseholdProfileIn) -> ChecklistResponse:
    household = HouseholdProfile(
        ownership=profile.ownership,
        has_pets=profile.has_pets,
        mobility_needs=profile.mobility_needs,
        construction_type=profile.construction_type,
    )
    result = generate_checklist(household)
    return ChecklistResponse(
        defensible_space=[ChecklistItemOut(text=i.text, reasons=i.reasons) for i in result.defensible_space],
        go_bag=[ChecklistItemOut(text=i.text, reasons=i.reasons) for i in result.go_bag],
        evacuation_route=[ChecklistItemOut(text=i.text, reasons=i.reasons) for i in result.evacuation_route],
        note=result.note,
    )
