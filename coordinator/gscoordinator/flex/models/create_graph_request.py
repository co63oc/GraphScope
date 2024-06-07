from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from gscoordinator.flex.models.base_model import Model
from gscoordinator.flex.models.create_graph_schema_request import CreateGraphSchemaRequest
from gscoordinator.flex.models.create_stored_proc_request import CreateStoredProcRequest
from gscoordinator.flex import util

from gscoordinator.flex.models.create_graph_schema_request import CreateGraphSchemaRequest  # noqa: E501
from gscoordinator.flex.models.create_stored_proc_request import CreateStoredProcRequest  # noqa: E501

class CreateGraphRequest(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, name=None, description=None, stored_procedures=None, _schema=None):  # noqa: E501
        """CreateGraphRequest - a model defined in OpenAPI

        :param name: The name of this CreateGraphRequest.  # noqa: E501
        :type name: str
        :param description: The description of this CreateGraphRequest.  # noqa: E501
        :type description: str
        :param stored_procedures: The stored_procedures of this CreateGraphRequest.  # noqa: E501
        :type stored_procedures: List[CreateStoredProcRequest]
        :param _schema: The _schema of this CreateGraphRequest.  # noqa: E501
        :type _schema: CreateGraphSchemaRequest
        """
        self.openapi_types = {
            'name': str,
            'description': str,
            'stored_procedures': List[CreateStoredProcRequest],
            '_schema': CreateGraphSchemaRequest
        }

        self.attribute_map = {
            'name': 'name',
            'description': 'description',
            'stored_procedures': 'stored_procedures',
            '_schema': 'schema'
        }

        self._name = name
        self._description = description
        self._stored_procedures = stored_procedures
        self.__schema = _schema

    @classmethod
    def from_dict(cls, dikt) -> 'CreateGraphRequest':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The CreateGraphRequest of this CreateGraphRequest.  # noqa: E501
        :rtype: CreateGraphRequest
        """
        return util.deserialize_model(dikt, cls)

    @property
    def name(self) -> str:
        """Gets the name of this CreateGraphRequest.


        :return: The name of this CreateGraphRequest.
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name: str):
        """Sets the name of this CreateGraphRequest.


        :param name: The name of this CreateGraphRequest.
        :type name: str
        """

        self._name = name

    @property
    def description(self) -> str:
        """Gets the description of this CreateGraphRequest.


        :return: The description of this CreateGraphRequest.
        :rtype: str
        """
        return self._description

    @description.setter
    def description(self, description: str):
        """Sets the description of this CreateGraphRequest.


        :param description: The description of this CreateGraphRequest.
        :type description: str
        """

        self._description = description

    @property
    def stored_procedures(self) -> List[CreateStoredProcRequest]:
        """Gets the stored_procedures of this CreateGraphRequest.


        :return: The stored_procedures of this CreateGraphRequest.
        :rtype: List[CreateStoredProcRequest]
        """
        return self._stored_procedures

    @stored_procedures.setter
    def stored_procedures(self, stored_procedures: List[CreateStoredProcRequest]):
        """Sets the stored_procedures of this CreateGraphRequest.


        :param stored_procedures: The stored_procedures of this CreateGraphRequest.
        :type stored_procedures: List[CreateStoredProcRequest]
        """

        self._stored_procedures = stored_procedures

    @property
    def _schema(self) -> CreateGraphSchemaRequest:
        """Gets the _schema of this CreateGraphRequest.


        :return: The _schema of this CreateGraphRequest.
        :rtype: CreateGraphSchemaRequest
        """
        return self.__schema

    @_schema.setter
    def _schema(self, _schema: CreateGraphSchemaRequest):
        """Sets the _schema of this CreateGraphRequest.


        :param _schema: The _schema of this CreateGraphRequest.
        :type _schema: CreateGraphSchemaRequest
        """

        self.__schema = _schema