"""DatabagModel class for writing custom databag models.

Contains utility methods for standardized serialization/deserialization of relation databag contents.
"""

import json
import logging
from typing import MutableMapping, Optional
# Note: MutableMapping is imported from the typing module and not collections.abc
# because subscripting collections.abc.MutableMapping was added in python 3.9, but
# most of our charms are based on 20.04, which has python 3.8.


import pydantic

logger = logging.getLogger("databag_model")

_RawDatabag = MutableMapping[str, str]


class DataValidationError(Exception):
    """Raised when relation databag validation fails."""


PYDANTIC_IS_V1 = int(pydantic.VERSION.split(".")[0]) < 2
if PYDANTIC_IS_V1:
    from pydantic import BaseModel

    class DatabagModel(BaseModel):  # type: ignore
        """Base databag model."""

        class Config:
            """Pydantic config."""

            # ignore any extra fields in the databag
            extra = "ignore"
            """Ignore any extra fields in the databag."""
            allow_population_by_field_name = True
            """Allow instantiating this class by field name (instead of forcing alias)."""

        @classmethod
        def load(cls, databag: _RawDatabag):
            """Load this model from a Juju databag."""
            try:
                data = {
                    k: json.loads(v)
                    for k, v in databag.items()
                    # Don't attempt to parse model-external values
                    if k in {f.alias for f in cls.__fields__.values()}  # type: ignore
                }
            except json.JSONDecodeError as e:
                msg = f"invalid databag contents: expecting json. {databag}"
                logger.error(msg)
                raise DataValidationError(msg) from e

            try:
                return cls.parse_raw(json.dumps(data))  # type: ignore
            except pydantic.ValidationError as e:
                msg = f"failed to validate databag: {databag}"
                # we can't know if this is a 'real error' because the remote side didn't do its job
                # or a transient state because the remote side didn't do its job *yet*.
                # logger.debug(msg, exc_info=True)
                raise DataValidationError(msg) from e

        def dump(self, to: Optional[_RawDatabag] = None, clear: bool = True):
            """Write the contents of this model to Juju databag.

            :param databag: the databag to write the data to.
            :param clear: ensure the databag is cleared before writing it.
            """
            if clear and to:
                to.clear()

            databag: _RawDatabag = to if to is not None else {}

            dct = self.dict()  # type: ignore
            for key, field in self.__fields__.items():  # type: ignore
                value = dct[key]
                databag[field.alias or key] = json.dumps(value)

            return databag

else:
    from pydantic import BaseModel, ConfigDict

    class DatabagModel(BaseModel):
        """Base databag model."""

        model_config = ConfigDict(
            # ignore any extra fields in the databag
            extra="ignore",
            # Allow instantiating this class by field name (instead of forcing alias).
            populate_by_name=True,
        )
        """Pydantic config."""

        @classmethod
        def load(cls, databag: _RawDatabag):
            """Load this model from a Juju databag."""
            try:
                data = {
                    k: json.loads(v)
                    for k, v in databag.items()
                    # Don't attempt to parse model-external values
                    if k in {(f.alias or n) for n, f in cls.__fields__.items()}  # type: ignore
                }
            except json.JSONDecodeError as e:
                msg = f"invalid databag contents: expecting json. {databag}"
                logger.error(msg)
                raise DataValidationError(msg) from e

            try:
                return cls.model_validate_json(json.dumps(data))  # type: ignore
            except pydantic.ValidationError as e:
                msg = f"failed to validate databag: {databag}"
                logger.debug(msg, exc_info=True)
                raise DataValidationError(msg) from e

        def dump(self, to: Optional[_RawDatabag] = None, clear: bool = True):
            """Write the contents of this model to Juju databag.

            :param to: the databag to write the data to.
            :param clear: ensure the databag is cleared before writing it.
            """
            if clear and to:
                to.clear()

            databag: _RawDatabag = to if to is not None else {}

            dct = self.model_dump(mode="json", by_alias=True, exclude_defaults=True)  # type: ignore
            databag.update({k: json.dumps(v) for k, v in dct.items()})
            return databag
