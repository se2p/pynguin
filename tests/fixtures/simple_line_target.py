def foo(x: int) -> int:
    if x > 0:
        return x + 1
    elif x == 0:
        return 0
    else:
        return x - 1


def bar(y: int) -> int:
    if y % 2 == 0:
        return y * 2
    return y + 3