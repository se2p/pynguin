#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

# Automatically generated by Pynguin.
import queue_example as module_0


def test_case_0():
    try:
        int_0 = -2944
        queue_0 = module_0.Queue(int_0)
    except BaseException:
        pass


def test_case_1():
    try:
        int_0 = 3390
        queue_0 = module_0.Queue(int_0)
        assert queue_0.head == 0
        assert queue_0.size == 0
        assert queue_0.tail == 0
        assert queue_0.max == 3390
        bool_0 = queue_0.full()
        int_1 = -475
        queue_1 = module_0.Queue(int_1)
    except BaseException:
        pass


def test_case_2():
    try:
        int_0 = 1769
        int_1 = 1080
        int_2 = 3
        queue_0 = module_0.Queue(int_2)
        assert queue_0.head == 0
        assert queue_0.size == 0
        assert queue_0.tail == 0
        assert queue_0.max == 3
        bool_0 = queue_0.full()
        bool_1 = queue_0.empty()
        int_3 = 1235
        bool_2 = queue_0.enqueue(int_3)
        assert bool_2 is True
        bool_3 = queue_0.empty()
        assert bool_3 is True
        bool_4 = queue_0.enqueue(int_0)
        assert bool_4 is True
        var_0 = queue_0.dequeue()
        assert var_0 == 1235
        var_1 = queue_0.dequeue()
        assert var_1 == 1769
        bool_5 = queue_0.enqueue(int_2)
        assert bool_5 is True
        var_2 = queue_0.dequeue()
        assert var_2 == 3
        queue_1 = module_0.Queue(int_1)
        assert queue_1.size == 0
        assert queue_1.tail == 0
        assert queue_1.max == 1080
        assert queue_1.head == 0
        var_3 = queue_1.dequeue()
        int_4 = -820
        queue_2 = module_0.Queue(int_4)
    except BaseException:
        pass


def test_case_3():
    try:
        int_0 = 1769
        int_1 = 3
        queue_0 = module_0.Queue(int_1)
        assert queue_0.size == 0
        assert queue_0.tail == 0
        assert queue_0.max == 3
        assert queue_0.head == 0
        bool_0 = queue_0.full()
        bool_1 = queue_0.empty()
        int_2 = 1272
        bool_2 = queue_0.enqueue(int_2)
        assert bool_2 is True
        int_3 = 435
        bool_3 = queue_0.enqueue(int_3)
        assert bool_3 is True
        bool_4 = queue_0.empty()
        assert bool_4 is True
        bool_5 = queue_0.enqueue(int_0)
        assert bool_5 is True
        var_0 = queue_0.dequeue()
        assert var_0 == 1272
        int_4 = 1021
        bool_6 = queue_0.enqueue(int_1)
        assert bool_6 is True
        bool_7 = queue_0.enqueue(int_4)
        var_1 = queue_0.dequeue()
        assert var_1 == 435
        bool_8 = queue_0.empty()
        assert bool_8 is True
        bool_9 = queue_0.empty()
        assert bool_9 is True
        int_5 = 688
        queue_1 = module_0.Queue(int_5)
        assert queue_1.head == 0
        assert queue_1.size == 0
        assert queue_1.tail == 0
        assert queue_1.max == 688
        bool_10 = queue_1.full()
        int_6 = 203
        queue_2 = module_0.Queue(int_6)
        assert queue_2.max == 203
        assert queue_2.tail == 0
        assert queue_2.head == 0
        assert queue_2.size == 0
        var_2 = queue_1.dequeue()
        var_3 = queue_2.dequeue()
        bool_11 = queue_1.empty()
        bool_12 = queue_2.empty()
        var_4 = queue_2.dequeue()
        int_7 = -256
        queue_3 = module_0.Queue(int_7)
    except BaseException:
        pass
