import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


def seed_test_case():
    var0 = not True
    var1 = not False
    var2 = module0.i_take_bools(var0, var1)
    assert var2 == 'Bools are different!'
