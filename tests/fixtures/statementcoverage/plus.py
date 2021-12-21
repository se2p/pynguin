class Plus:
    calculations = 0

    def plus_three(self, number):
        self.calculations += 1
        return number + 3

    def plus_four(self, number):
        self.calculations += 1
        return number + 4
