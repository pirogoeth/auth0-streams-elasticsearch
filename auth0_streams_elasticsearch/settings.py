# -*- coding: utf-8 -*-

import os
from typing import Any, Optional

import aiomisc


def strbool(s: str) -> bool:
    s = s.lower()
    if s in ["t", "true", "yes", "y", "1"]:
        return True
    elif s in ["f", "false", "no", "n", "0"]:
        return False
    else:
        raise ValueError(f"{s} can not be converted to boolean")


class Settings:
    """ Settings contains all setting defaults.
        When an attribute is accessed on an instance of Settings,
        values from `os.environ` will be returned first, if they exist.
    """

    defaults = {
        "BEARER_TOKEN": None,
        "BIND_ADDRESS": "0.0.0.0",
        "BIND_PORT": "3000",
        "ELASTICSEARCH_INDEX_NAME": "auth0-events-%Y.%m.%d",
        "ELASTICSEARCH_PASSWORD": None,
        "ELASTICSEARCH_SSL_VERIFY": "true",
        "ELASTICSEARCH_URL": "http://localhost:9200",
        "ELASTICSEARCH_USERNAME": None,
        "QUEUE_MAX_SIZE": "50",
        "SEND_AFTER_EVENTS": "10",
        "SEND_AFTER_TIME": "5",
        "SEND_LOOP_WAIT": "1e7",
    }

    converters = {
        "BIND_PORT": int,
        "ELASTICSEARCH_SSL_VERIFY": strbool,
        "QUEUE_MAX_SIZE": int,
        "QUEUE_MAX_TIME": int,
        "SEND_AFTER_EVENTS": int,
        "SEND_AFTER_TIME": int,
        "SEND_LOOP_WAIT": float,
    }

    def __init__(self):
        # Check for required setting values at initialization
        for setting in Settings.defaults.keys():
            self.__getattr__(setting)

    def __getattr__(self, name) -> Any:
        value = self.get_value(name)
        if value is None:
            # This is a setting that we can not set a sane default for.
            # When a value is none, we should raise
            raise SettingUnset(name)

        if (converter := Settings.converters.get(name)) is not None:
            try:
                return converter(value)
            except Exception as err:
                raise WrongSettingType(name) from err

        return value

    def get_value(self, name) -> Any:
        """ Returns the setting value for `name`.
        """

        try:
            return os.environ[name]
        except KeyError:
            return Settings.defaults[name]


class SettingUnset(Exception):

    def __init__(self, setting_name: str):
        super().__init__(f"Setting is required, but unset: {setting_name}")


class WrongSettingType(Exception):

    def __init__(self, setting_name: str):
        super().__init__(f"Setting {setting_name} could not be converted to correct type")
