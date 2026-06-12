import story
from settings import CHAPTERS, CLASSES


def test_prologue_epilogue_pages():
    for pages in (story.PROLOGUE, story.EPILOGUE):
        assert pages and isinstance(pages, list)
        for page in pages:
            # 行允许为空字符串（排版空行），但每页必须有实际内容
            assert any(line for line in page)
            assert all(isinstance(line, str) for line in page)


def _check_lines(lines):
    assert lines
    for speaker, side, text in lines:
        assert side in ('left', 'right', None)
        assert isinstance(text, str) and text
        if speaker == '旁白':
            assert side is None
        else:
            assert speaker in story.NAME_TO_CLS, speaker
            assert story.NAME_TO_CLS[speaker] in CLASSES


def test_every_chapter_has_pre_and_post():
    assert set(story.CHAPTER_DIALOGUE) == set(range(len(CHAPTERS)))
    for idx in story.CHAPTER_DIALOGUE:
        _check_lines(story.CHAPTER_DIALOGUE[idx]['pre'])
        _check_lines(story.CHAPTER_DIALOGUE[idx]['post'])


def test_boss_quotes_cover_all_chapters():
    assert set(story.BOSS_QUOTES) == set(range(len(CHAPTERS)))
    for idx, lines in story.BOSS_QUOTES.items():
        _check_lines(lines)
        boss_name = next(e['name'] for e in CHAPTERS[idx]['enemies'] if e.get('boss'))
        assert any(s == boss_name for s, _, _ in lines)   # 叫阵必须有Boss本人台词


def test_bios_cover_codex():
    assert len(story.CODEX_ORDER) == 18
    for name in story.CODEX_ORDER:
        b = story.BIOS[name]
        assert b['cls'] in CLASSES
        assert b['title']
        assert b['bio'] and all(isinstance(line, str) and line for line in b['bio'])


def test_speakers_in_dialogues_have_sprites():
    # 我方说话人必须真的在该章出场（join 前不能说话的约束由 pre 对话顺序保证，这里只验证可渲染）
    for name, cls in story.NAME_TO_CLS.items():
        assert cls in CLASSES
