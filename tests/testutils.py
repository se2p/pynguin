#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Some utilites to make testing easier."""
import pynguin.utils.generic.genericaccessibleobject as gao

from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TypeSystem


def feed_typesystem(system: TypeSystem, generic: gao.GenericAccessibleObject):
    """Small helper because TypeInfos need to be aligned, and we don't have one
    large typesystem during testing but create them in various places."""

    # TODO(fk) think about making this less hacky.
    def feed(typ: ProperType):
        if isinstance(typ, Instance):
            system.to_type_info(typ.type.raw_type)

    if isinstance(generic, gao.GenericCallableAccessibleObject):
        feed(generic.inferred_signature.return_type)
        for para in generic.inferred_signature.original_parameters.values():
            feed(para)

    if isinstance(generic, gao.GenericConstructor):
        assert generic.owner
        system.to_type_info(generic.owner.raw_type)

    if isinstance(generic, gao.GenericField):
        system.to_type_info(generic.owner.raw_type)
