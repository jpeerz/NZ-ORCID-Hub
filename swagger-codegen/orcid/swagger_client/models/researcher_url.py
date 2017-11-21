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


class ResearcherUrl(object):
    """
    NOTE: This class is auto generated by the swagger code generator program.
    Do not edit the class manually.
    """
    def __init__(self, created_date=None, last_modified_date=None, source=None, url_name=None, url=None, visibility=None, path=None, put_code=None, display_index=None):
        """
        ResearcherUrl - a model defined in Swagger

        :param dict swaggerTypes: The key is attribute name
                                  and the value is attribute type.
        :param dict attributeMap: The key is attribute name
                                  and the value is json key in definition.
        """
        self.swagger_types = {
            'created_date': 'CreatedDate',
            'last_modified_date': 'LastModifiedDate',
            'source': 'Source',
            'url_name': 'str',
            'url': 'Url',
            'visibility': 'str',
            'path': 'str',
            'put_code': 'int',
            'display_index': 'int'
        }

        self.attribute_map = {
            'created_date': 'created-date',
            'last_modified_date': 'last-modified-date',
            'source': 'source',
            'url_name': 'url-name',
            'url': 'url',
            'visibility': 'visibility',
            'path': 'path',
            'put_code': 'put-code',
            'display_index': 'display-index'
        }

        self._created_date = created_date
        self._last_modified_date = last_modified_date
        self._source = source
        self._url_name = url_name
        self._url = url
        self._visibility = visibility
        self._path = path
        self._put_code = put_code
        self._display_index = display_index

    @property
    def created_date(self):
        """
        Gets the created_date of this ResearcherUrl.

        :return: The created_date of this ResearcherUrl.
        :rtype: CreatedDate
        """
        return self._created_date

    @created_date.setter
    def created_date(self, created_date):
        """
        Sets the created_date of this ResearcherUrl.

        :param created_date: The created_date of this ResearcherUrl.
        :type: CreatedDate
        """

        self._created_date = created_date

    @property
    def last_modified_date(self):
        """
        Gets the last_modified_date of this ResearcherUrl.

        :return: The last_modified_date of this ResearcherUrl.
        :rtype: LastModifiedDate
        """
        return self._last_modified_date

    @last_modified_date.setter
    def last_modified_date(self, last_modified_date):
        """
        Sets the last_modified_date of this ResearcherUrl.

        :param last_modified_date: The last_modified_date of this ResearcherUrl.
        :type: LastModifiedDate
        """

        self._last_modified_date = last_modified_date

    @property
    def source(self):
        """
        Gets the source of this ResearcherUrl.

        :return: The source of this ResearcherUrl.
        :rtype: Source
        """
        return self._source

    @source.setter
    def source(self, source):
        """
        Sets the source of this ResearcherUrl.

        :param source: The source of this ResearcherUrl.
        :type: Source
        """

        self._source = source

    @property
    def url_name(self):
        """
        Gets the url_name of this ResearcherUrl.

        :return: The url_name of this ResearcherUrl.
        :rtype: str
        """
        return self._url_name

    @url_name.setter
    def url_name(self, url_name):
        """
        Sets the url_name of this ResearcherUrl.

        :param url_name: The url_name of this ResearcherUrl.
        :type: str
        """

        self._url_name = url_name

    @property
    def url(self):
        """
        Gets the url of this ResearcherUrl.

        :return: The url of this ResearcherUrl.
        :rtype: Url
        """
        return self._url

    @url.setter
    def url(self, url):
        """
        Sets the url of this ResearcherUrl.

        :param url: The url of this ResearcherUrl.
        :type: Url
        """

        self._url = url

    @property
    def visibility(self):
        """
        Gets the visibility of this ResearcherUrl.

        :return: The visibility of this ResearcherUrl.
        :rtype: str
        """
        return self._visibility

    @visibility.setter
    def visibility(self, visibility):
        """
        Sets the visibility of this ResearcherUrl.

        :param visibility: The visibility of this ResearcherUrl.
        :type: str
        """
        allowed_values = ["LIMITED", "REGISTERED_ONLY", "PUBLIC"]
        if visibility not in allowed_values:
            raise ValueError(
                "Invalid value for `visibility` ({0}), must be one of {1}"
                .format(visibility, allowed_values)
            )

        self._visibility = visibility

    @property
    def path(self):
        """
        Gets the path of this ResearcherUrl.

        :return: The path of this ResearcherUrl.
        :rtype: str
        """
        return self._path

    @path.setter
    def path(self, path):
        """
        Sets the path of this ResearcherUrl.

        :param path: The path of this ResearcherUrl.
        :type: str
        """

        self._path = path

    @property
    def put_code(self):
        """
        Gets the put_code of this ResearcherUrl.

        :return: The put_code of this ResearcherUrl.
        :rtype: int
        """
        return self._put_code

    @put_code.setter
    def put_code(self, put_code):
        """
        Sets the put_code of this ResearcherUrl.

        :param put_code: The put_code of this ResearcherUrl.
        :type: int
        """

        self._put_code = put_code

    @property
    def display_index(self):
        """
        Gets the display_index of this ResearcherUrl.

        :return: The display_index of this ResearcherUrl.
        :rtype: int
        """
        return self._display_index

    @display_index.setter
    def display_index(self, display_index):
        """
        Sets the display_index of this ResearcherUrl.

        :param display_index: The display_index of this ResearcherUrl.
        :type: int
        """

        self._display_index = display_index

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
        if not isinstance(other, ResearcherUrl):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """
        Returns true if both objects are not equal
        """
        return not self == other
