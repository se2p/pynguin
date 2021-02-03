import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


def seed_test_case():
    var0 = True
    var1 = True
    var2 = module0.i_take_bools(var0, var1)
    assert var2 == "Bools are equal!"
