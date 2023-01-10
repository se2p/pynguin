#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import json

import pytest

import pynguin.configuration as config
from pynguin.analyses.type4py_api import find_predicted_signature, query_type4py_api


def test_type4py_api(requests_mock):
    config.configuration.type_inference.type4py_uri = "mock://bar/"
    requests_mock.post("mock://bar/api/predict?tc=0&fp=0", text="{}")
    assert query_type4py_api("foo", "bar") == {}


@pytest.fixture()
def type4py_data():
    return json.loads(
        """{
       "error":null,
       "response":{
          "classes":[
             {
                "cls_var_ln":{
                   "cls_var_name":[
                      [
                         4,
                         4
                      ],
                      [
                         4,
                         13
                      ]
                   ]
                },
                "cls_var_occur":{
                   "cls_var_name":[
                      [
                         "token",
                         "var",
                         "name"
                      ]
                   ]
                },
                "funcs":[
                   {
                      "docstring":{
                         "func":"None",
                         "long_descr":"None",
                         "ret":"None"
                      },
                      "fn_lc":[
                         [
                            5,
                            4
                         ],
                         [
                            8,
                            28
                         ]
                      ],
                      "fn_var_ln":{
                         "var_name":[
                            [
                               7,
                               8
                            ],
                            [
                               7,
                               16
                            ]
                         ]
                      },
                      "fn_var_occur":{
                         "var_name":[
                            [
                               "token",
                               "var",
                               "name"
                            ]
                         ]
                      },
                      "name":"__init__",
                      "params":{
                         "age":"int"
                      },
                      "params_descr":{
                         "age":"comment"
                      },
                      "params_occur":{
                         "age":[
                            [
                               "self",
                               "age",
                               "age"
                            ]
                         ]
                      },
                      "params_p":{
                         "age":[
                            [
                               "int",
                               0.9999999991180025
                            ],
                            [
                               "str",
                               2.3463255785983247e-10
                            ]
                         ]
                      },
                      "q_name":"Person.__init__",
                      "ret_exprs":[
                         ""
                      ],
                      "ret_type":"None",
                      "variables":{
                         "age":""
                      },
                      "variables_p":{
                         "age":[
                            [
                               "int",
                               0.2801499039103035
                            ]
                         ]
                      }
                   },
                   {
                      "docstring":{
                         "func":"None",
                         "long_descr":"None",
                         "ret":"None"
                      },
                      "fn_lc":[
                         [
                            10,
                            4
                         ],
                         [
                            11,
                            24
                         ]
                      ],
                      "fn_var_ln":{

                      },
                      "fn_var_occur":{

                      },
                      "name":"get_name",
                      "params":{

                      },
                      "params_descr":{

                      },
                      "params_occur":{

                      },
                      "params_p":{

                      },
                      "q_name":"Person.get_name",
                      "ret_exprs":[
                         "return self.name"
                      ],
                      "ret_type":"",
                      "ret_type_p":[
                         [
                            "str",
                            0.7073830464758581
                         ]
                      ],
                      "variables":{

                      },
                      "variables_p":{

                      }
                   }
                ],
                "name":"Person",
                "q_name":"Person",
                "variables":{
                   "person_id":""
                },
                "variables_p":{
                   "person_id":[
                      [
                         "str",
                         0.703074717210447
                      ]
                   ]
                }
             }
          ],
          "funcs":[
             {
                "docstring":{
                   "func":"None",
                   "long_descr":"None",
                   "ret":"None"
                },
                "fn_lc":[
                   [
                      18,
                      0
                   ],
                   [
                      25,
                      18
                   ]
                ],
                "fn_var_ln":{
                   "leave_hours":[
                      [
                         19,
                         4
                      ],
                      [
                         19,
                         15
                      ]
                   ]
                },
                "fn_var_occur":{
                   "leave_hours":[
                      [
                         "no_hours",
                         "leave_hours"
                      ]
                   ]
                },
                "name":"work",
                "params":{
                   "no_hours":""
                },
                "params_descr":{
                   "no_hours":""
                },
                "params_occur":{
                   "no_hours":[
                      [
                         "no_hours",
                         "leave_hours"
                      ]
                   ]
                },
                "params_p":{
                   "no_hours":[
                      [
                         "Type",
                         0.0999
                      ]
                   ]
                },
                "q_name":"work",
                "ret_exprs":[
                   "return 'Done!'"
                ],
                "ret_type":"",
                "ret_type_p":[
                   [
                      "str",
                      0.287441260068372
                   ]
                ],
                "variables":{
                   "leave_hours":""
                },
                "variables_p":{
                   "leave_hours":[
                      [
                         "int",
                         0.2
                      ]
                   ]
                }
             }
          ],
          "imports":[
             "os"
          ],
          "mod_var_ln":{
             "A_GLOBAL_VAR":[
                [
                   1,
                   0
                ],
                [
                   1,
                   12
                ]
             ]
          },
          "mod_var_occur":{
             "A_GLOBAL_VAR":[
                "token"
             ]
          },
          "no_types_annot":{
             "D":1,
             "I":0,
             "U":14
          },
          "session_id":"a0bvkdCC8utA35r8JrOho07FrDpV9qaLr2lccFzoXB4",
          "set":"None",
          "tc":[
             false,
             "None"
          ],
          "type_annot_cove":0.07,
          "typed_seq":"",
          "untyped_seq":"",
          "variables":{
             "A_GLOBAL_VAR":""
          },
          "variables_p":{
             "A_GLOBAL_VAR":[
                [
                   "str",
                   0.41389838221497904
                ]
             ]
          }
       }
    }"""
    )


def test_find_predicted_signature_param(type4py_data):
    result = find_predicted_signature(type4py_data, "work")
    assert result["params_p"]["no_hours"] == [["Type", 0.0999]]


def test_find_predicted_signature_ret(type4py_data):
    result = find_predicted_signature(type4py_data, "Person.get_name", "Person")
    assert result["ret_type_p"] == [["str", 0.7073830464758581]]
