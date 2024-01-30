# coding: utf-8

"""
    GraphScope FLEX HTTP SERVICE API

    This is a specification for GraphScope FLEX HTTP service based on the OpenAPI 3.0 specification. You can find out more details about specification at [doc](https://swagger.io/specification/v3/).  Some useful links: - [GraphScope Repository](https://github.com/alibaba/GraphScope) - [The Source API definition for GraphScope Interactive](https://github.com/GraphScope/portal/tree/main/httpservice)

    The version of the OpenAPI document: 0.9.1
    Contact: graphscope@alibaba-inc.com
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


from __future__ import annotations
import pprint
import re  # noqa: F401
import json


from typing import Any, ClassVar, Dict, List, Optional
from pydantic import BaseModel, StrictInt, StrictStr
from pydantic import Field
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

class DeploymentStatus(BaseModel):
    """
    K8s only
    """ # noqa: E501
    name: Optional[StrictStr] = None
    container: Optional[List[StrictStr]] = None
    image: Optional[List[StrictStr]] = None
    labels: Optional[List[StrictStr]] = None
    node: Optional[StrictStr] = None
    status: Optional[StrictStr] = None
    restart_count: Optional[StrictInt] = None
    cpu_value: Optional[StrictInt] = Field(default=None, description="cpu value in millicore")
    memory_value: Optional[StrictInt] = Field(default=None, description="memory value in megabytes")
    timestamp: Optional[StrictStr] = None
    creation_time: Optional[StrictStr] = None
    __properties: ClassVar[List[str]] = ["name", "container", "image", "labels", "node", "status", "restart_count", "cpu_value", "memory_value", "timestamp", "creation_time"]

    model_config = {
        "populate_by_name": True,
        "validate_assignment": True,
        "protected_namespaces": (),
    }


    def to_str(self) -> str:
        """Returns the string representation of the model using alias"""
        return pprint.pformat(self.model_dump(by_alias=True))

    def to_json(self) -> str:
        """Returns the JSON representation of the model using alias"""
        # TODO: pydantic v2: use .model_dump_json(by_alias=True, exclude_unset=True) instead
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> Self:
        """Create an instance of DeploymentStatus from a JSON string"""
        return cls.from_dict(json.loads(json_str))

    def to_dict(self) -> Dict[str, Any]:
        """Return the dictionary representation of the model using alias.

        This has the following differences from calling pydantic's
        `self.model_dump(by_alias=True)`:

        * `None` is only added to the output dict for nullable fields that
          were set at model initialization. Other fields with value `None`
          are ignored.
        """
        _dict = self.model_dump(
            by_alias=True,
            exclude={
            },
            exclude_none=True,
        )
        return _dict

    @classmethod
    def from_dict(cls, obj: Dict) -> Self:
        """Create an instance of DeploymentStatus from a dict"""
        if obj is None:
            return None

        if not isinstance(obj, dict):
            return cls.model_validate(obj)

        _obj = cls.model_validate({
            "name": obj.get("name"),
            "container": obj.get("container"),
            "image": obj.get("image"),
            "labels": obj.get("labels"),
            "node": obj.get("node"),
            "status": obj.get("status"),
            "restart_count": obj.get("restart_count"),
            "cpu_value": obj.get("cpu_value"),
            "memory_value": obj.get("memory_value"),
            "timestamp": obj.get("timestamp"),
            "creation_time": obj.get("creation_time")
        })
        return _obj


