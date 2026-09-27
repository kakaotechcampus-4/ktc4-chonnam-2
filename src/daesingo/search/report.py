from pydantic import BaseModel

from .privacy import mask_license_plates


def render_report(model: BaseModel) -> str:
    return mask_license_plates(model.model_dump_json(indent=2))
