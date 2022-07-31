#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Some utilites to make testing easier."""
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.typesystem import Instance, ProperType, TypeSystem


def __feed_typesystem(system: TypeSystem, generic: gao.GenericAccessibleObject):
    """Small helper because TypeInfos need to be aligned, because we don't have one
    large typesystem during testing but create them in various places."""

    # TODO(fk) think about making this less hacky.
    def feed(typ: ProperType):
        if isinstance(typ, Instance):
            system.to_type_info(typ.type.raw_type)

    if isinstance(generic, gao.GenericCallableAccessibleObject):
        feed(generic.inferred_signature.return_type)
        for para in generic.inferred_signature.parameters.values():
            feed(para)

    if isinstance(generic, gao.GenericConstructor):
        assert generic.owner
        system.to_type_info(generic.owner.raw_type)

    if isinstance(generic, gao.GenericField):
        system.to_type_info(generic.owner.raw_type)
