# Dummy method for testing adding a value
def compare_op_dummy(x, y):
    if x == y:
        return 0
    else:
        return 1


# Dummy method for testing the str.startswith method
def startswith_dummy(s1, s2):
    if s1.startswith(s2):
        return 0
    else:
        return 1


# Dummy method for testing the str.endswith method
def endswith_dummy(s1, s2):
    if s1.endswith(s2):
        return 0
    else:
        return 1


# Dummy method for testing the str.isalnum() method
def isalnum_dummy(s1):
    if not isinstance(s1, str):
        return 2
    if s1.isalnum():
        return 0
    else:
        return 1
