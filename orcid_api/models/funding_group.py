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


class FundingGroup(object):
    """
    NOTE: This class is auto generated by the swagger code generator program.
    Do not edit the class manually.
    """
    def __init__(self, last_modified_date=None, external_ids=None, funding_summary=None):
        """
        FundingGroup - a model defined in Swagger

        :param dict swaggerTypes: The key is attribute name
                                  and the value is attribute type.
        :param dict attributeMap: The key is attribute name
                                  and the value is json key in definition.
        """
        self.swagger_types = {
            'last_modified_date': 'LastModifiedDate',
            'external_ids': 'ExternalIDs',
            'funding_summary': 'list[FundingSummary]'
        }

        self.attribute_map = {
            'last_modified_date': 'last-modified-date',
            'external_ids': 'external-ids',
            'funding_summary': 'funding-summary'
        }

        self._last_modified_date = last_modified_date
        self._external_ids = external_ids
        self._funding_summary = funding_summary

    @property
    def last_modified_date(self):
        """
        Gets the last_modified_date of this FundingGroup.

        :return: The last_modified_date of this FundingGroup.
        :rtype: LastModifiedDate
        """
        return self._last_modified_date

    @last_modified_date.setter
    def last_modified_date(self, last_modified_date):
        """
        Sets the last_modified_date of this FundingGroup.

        :param last_modified_date: The last_modified_date of this FundingGroup.
        :type: LastModifiedDate
        """

        self._last_modified_date = last_modified_date

    @property
    def external_ids(self):
        """
        Gets the external_ids of this FundingGroup.

        :return: The external_ids of this FundingGroup.
        :rtype: ExternalIDs
        """
        return self._external_ids

    @external_ids.setter
    def external_ids(self, external_ids):
        """
        Sets the external_ids of this FundingGroup.

        :param external_ids: The external_ids of this FundingGroup.
        :type: ExternalIDs
        """

        self._external_ids = external_ids

    @property
    def funding_summary(self):
        """
        Gets the funding_summary of this FundingGroup.

        :return: The funding_summary of this FundingGroup.
        :rtype: list[FundingSummary]
        """
        return self._funding_summary

    @funding_summary.setter
    def funding_summary(self, funding_summary):
        """
        Sets the funding_summary of this FundingGroup.

        :param funding_summary: The funding_summary of this FundingGroup.
        :type: list[FundingSummary]
        """

        self._funding_summary = funding_summary

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
        if not isinstance(other, FundingGroup):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """
        Returns true if both objects are not equal
        """
        return not self == other
