# Dummy method for testing the str.isalnum() function
def isalnum_test(s1: str) -> int:
    if not isinstance(s1, str):
        return 100
    if s1.isalnum():
        return 0
    else:
        return 1
