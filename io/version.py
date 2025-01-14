from typing import Optional
from pydantic import BaseModel


VersionID = str


#class Scores(BaseModel):
#    precision: float
#    recall: float

class Scores(BaseModel):
    f1_macro: Optional[float]
    f1_micro: Optional[float]
    f1_weighted: Optional[float]


class ModelVersion(BaseModel):
    version: Optional[VersionID]
    scores: Optional[Scores]


class ModelDescription(BaseModel):
    model: str
    description: Optional[str]
    version: ModelVersion = None