from app.core.models import Photo, Tag

def test_photo_has_required_fields():
    p = Photo(
        id=1,
        relative_path="2024/IMG_001.jpg",
        filename="IMG_001.jpg",
        file_size=1024,
    )
    assert p.id == 1
    assert p.relative_path == "2024/IMG_001.jpg"
    assert p.shot_at is None
    assert p.width is None

def test_tag_default_status_none():
    t = Tag(photo_id=1)
    assert t.status is None
    assert t.color is None
