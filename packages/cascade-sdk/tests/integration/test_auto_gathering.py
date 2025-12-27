import cascade as cs


@cs.task(pure=True)
def task_one():
    return 1


@cs.task(pure=True)
def task_two():
    return "two"


@cs.task(pure=True)
def identity(val: any) -> any:
    return val


def test_run_with_list_of_lazy_results():
    lr1 = task_one()
    lr2 = task_two()

    # This is the proposed intuitive usage
    results = cs.run([lr1, lr2])

    assert results == [1, "two"]


def test_run_with_tuple_of_lazy_results():
    lr1 = task_one()
    lr2 = task_two()

    results = cs.run((lr1, lr2))

    # Per the proposal, the return type is unified to a list
    assert results == [1, "two"]


def test_run_with_mixed_list_of_lazy_results_and_literals():
    lr1 = task_one()
    literal_str = "I am a literal"
    lr2 = task_two()

    # The graph should effectively be gather(lr1, identity("..."), lr2)
    results = cs.run([lr1, literal_str, lr2])

    assert results == [1, "I am a literal", "two"]


def test_run_with_empty_list():
    results = cs.run([])
    assert results == []
