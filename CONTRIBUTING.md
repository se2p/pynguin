# How to contribute

## Dependencies

We use `poetry` to manage the [dependencies](https://github.com/python-poetry/poetry).
If you do not have `poetry` installed, you should run the command below.

```bash
make download-poetry
```

To install dependencies and prepare [`pre-commit`](https://pre-commit.com/) hooks you would need to run `install` command:

```bash
make install
```

To activate your `virtualenv` run `poetry shell`.

## Codestyle

After you run `make install` you can execute the automatic code formatting.

```bash
make codestyle
```

### Checks

Many checks are configured for this project.
Command `make check-style` will run black diffs,
darglint docstring style and mypy.
The `make check-safety` command will look at the security of your code.

You can also use `STRICT=1` flag to make the check be strict.

### Before submitting

Before submitting your code please do the following steps:

1. Add any changes you want
1. Add tests for the new changes
1. Edit documentation if you have changed something significant
1. Run `make codestyle` to format your changes.
1. Run `STRICT=1 make check-style` to ensure that types and docs are correct
1. Run `STRICT=1 make check-safety` to ensure that security of your code is correct

## Other help

You can contribute by spreading a word about this library.
It would also be a huge contribution to write
a short article on how you are using this project.
You can also share your best practices with us.
