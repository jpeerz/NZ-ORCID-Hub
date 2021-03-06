# coding: utf-8

"""
    ORCID Member

    No description provided (generated by Swagger Codegen https://github.com/swagger-api/swagger-codegen)

    OpenAPI spec version: Latest
    
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""


from pprint import pformat
from six import iteritems
import re


class FundingContributorAttributes(object):
    """
    NOTE: This class is auto generated by the swagger code generator program.
    Do not edit the class manually.
    """
    def __init__(self, contributor_role=None):
        """
        FundingContributorAttributes - a model defined in Swagger

        :param dict swaggerTypes: The key is attribute name
                                  and the value is attribute type.
        :param dict attributeMap: The key is attribute name
                                  and the value is json key in definition.
        """
        self.swagger_types = {
            'contributor_role': 'str'
        }

        self.attribute_map = {
            'contributor_role': 'contributor-role'
        }

        self._contributor_role = contributor_role

    @property
    def contributor_role(self):
        """
        Gets the contributor_role of this FundingContributorAttributes.

        :return: The contributor_role of this FundingContributorAttributes.
        :rtype: str
        """
        return self._contributor_role

    @contributor_role.setter
    def contributor_role(self, contributor_role):
        """
        Sets the contributor_role of this FundingContributorAttributes.

        :param contributor_role: The contributor_role of this FundingContributorAttributes.
        :type: str
        """
        allowed_values = ["LEAD", "CO_LEAD", "SUPPORTED_BY", "OTHER_CONTRIBUTION"]
        if contributor_role not in allowed_values:
            raise ValueError(
                "Invalid value for `contributor_role` ({0}), must be one of {1}"
                .format(contributor_role, allowed_values)
            )

        self._contributor_role = contributor_role

    def to_dict(self):
        """
        Returns the model properties as a dict
        """
        result = {}

        for attr, _ in iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value

        return result

    def to_str(self):
        """
        Returns the string representation of the model
        """
        return pformat(self.to_dict())

    def __repr__(self):
        """
        For `print` and `pprint`
        """
        return self.to_str()

    def __eq__(self, other):
        """
        Returns true if both objects are equal
        """
        if not isinstance(other, FundingContributorAttributes):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """
        Returns true if both objects are not equal
        """
        return not self == other
