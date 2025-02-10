import argparse

def foo():
    pass

if not __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input')
    args = parser.parse_args()
