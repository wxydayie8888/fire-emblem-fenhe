import guide


def test_pages_well_formed():
    pages = guide.pages()
    assert len(pages) == 7
    titles = [t for t, _ in pages]
    assert '操作 · 键位' in titles and '职业 · 转职' in titles
    assert '世界观 · 史话' in titles
    for title, paras in pages:
        assert title
        for para in paras:
            assert para[0] in ('h', 'p', 'kv', 'gap')
            if para[0] == 'kv':
                assert len(para[1]) == 2


def test_support_convos_for_all_pairs():
    import story
    import supports
    for a, b in supports.SUPPORT_PAIRS:
        convo = story.support_convo(a, b)
        assert convo, (a, b)
        for speaker, text in convo:
            assert speaker and text


def test_promotion_page_covers_all():
    import settings
    promo = dict(guide.pages())['职业 · 转职']
    kvs = [p[1][0] for p in promo if p[0] == 'kv']
    assert len(kvs) == len(settings.PROMOTIONS)   # 8 条转职树


def test_supports_page_lists_pairs():
    import supports
    sup = dict(guide.pages())['羁绊']
    kvs = [p for p in sup if p[0] == 'kv']
    assert len(kvs) == len(supports.SUPPORT_PAIRS)
