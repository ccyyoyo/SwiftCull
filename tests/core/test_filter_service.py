from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.tag_service import TagService
from app.core.filter_service import FilterService
from app.core.models import Photo

def _insert_photo(db_conn, rel_path):
    return PhotoRepository(db_conn).insert(
        Photo(id=None, relative_path=rel_path, filename=rel_path, file_size=1)
    )

def test_filter_by_status_pick(db_conn):
    p1 = _insert_photo(db_conn, "f1.jpg")
    p2 = _insert_photo(db_conn, "f2.jpg")
    p3 = _insert_photo(db_conn, "f3.jpg")
    tag_svc = TagService(TagRepository(db_conn))
    tag_svc.set_status(p1, "pick")
    tag_svc.set_status(p2, "reject")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter(statuses=["pick"])
    ids = {p.id for p in result}
    assert p1 in ids
    assert p2 not in ids
    assert p3 not in ids

def test_filter_untagged_returns_no_tag_photos(db_conn):
    p1 = _insert_photo(db_conn, "u1.jpg")
    p2 = _insert_photo(db_conn, "u2.jpg")
    TagService(TagRepository(db_conn)).set_status(p2, "pick")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter(statuses=["untagged"])
    ids = {p.id for p in result}
    assert p1 in ids
    assert p2 not in ids

def test_filter_by_color(db_conn):
    p1 = _insert_photo(db_conn, "c1.jpg")
    p2 = _insert_photo(db_conn, "c2.jpg")
    TagService(TagRepository(db_conn)).set_color(p1, "red")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter(colors=["red"])
    ids = {p.id for p in result}
    assert p1 in ids
    assert p2 not in ids

def test_no_filter_returns_all(db_conn):
    for i in range(3):
        _insert_photo(db_conn, f"all{i}.jpg")
    svc = FilterService(PhotoRepository(db_conn), TagRepository(db_conn))
    result = svc.filter()
    assert len(result) == 3

def test_filter_blur_blurry(db_conn):
    photo_repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(photo_repo, tag_repo)

    pid_blurry = _insert_with_blur(photo_repo, "blurry.jpg", 5.0)
    pid_sharp = _insert_with_blur(photo_repo, "sharp.jpg", 500.0)

    results = svc.filter(blur=["blurry"], blur_fixed_threshold=100.0)
    ids = [p.id for p in results]
    assert pid_blurry in ids
    assert pid_sharp not in ids

def test_filter_blur_unanalyzed(db_conn):
    photo_repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(photo_repo, tag_repo)

    pid_none = _insert_with_blur(photo_repo, "none.jpg", None)
    pid_scored = _insert_with_blur(photo_repo, "scored.jpg", 200.0)

    results = svc.filter(blur=["unanalyzed"])
    ids = [p.id for p in results]
    assert pid_none in ids
    assert pid_scored not in ids


def _insert_with_blur(repo, path, blur_score):
    from app.core.models import Photo
    pid = repo.insert(Photo(id=None, relative_path=path, filename=path, file_size=1))
    if blur_score is not None:
        repo.update_blur_score(pid, blur_score)
    return pid

def test_blur_filter_or_logic_blurry_and_sharp(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)
    pid_blurry = _insert_with_blur(repo, "b.jpg", 10.0)
    pid_sharp  = _insert_with_blur(repo, "s.jpg", 500.0)
    # Selecting both blurry+sharp should return both (OR), not empty (AND-exclusion)
    results = svc.filter(blur=["blurry", "sharp"], blur_fixed_threshold=100.0)
    ids = [p.id for p in results]
    assert pid_blurry in ids
    assert pid_sharp in ids

def test_blur_filter_or_logic_unanalyzed_and_sharp(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)
    pid_none  = _insert_with_blur(repo, "n.jpg", None)
    pid_sharp = _insert_with_blur(repo, "s.jpg", 500.0)
    results = svc.filter(blur=["unanalyzed", "sharp"], blur_fixed_threshold=100.0)
    ids = [p.id for p in results]
    assert pid_none in ids
    assert pid_sharp in ids

def test_blur_filter_relative_mode(db_conn):
    from app.db.photo_repository import PhotoRepository
    from app.db.tag_repository import TagRepository
    from app.core.filter_service import FilterService
    repo = PhotoRepository(db_conn)
    tag_repo = TagRepository(db_conn)
    svc = FilterService(repo, tag_repo)
    pid_low  = _insert_with_blur(repo, "low.jpg", 5.0)
    pid_mid  = _insert_with_blur(repo, "mid.jpg", 50.0)
    pid_high = _insert_with_blur(repo, "hi.jpg", 500.0)
    # bottom 40% of [5.0, 50.0, 500.0] → idx=0 → threshold=5.0+eps → only 5.0 is blurry
    results = svc.filter(
        blur=["blurry"],
        blur_mode="relative",
        blur_relative_percent=40.0,
    )
    ids = [p.id for p in results]
    assert pid_low in ids
    assert pid_mid not in ids
    assert pid_high not in ids
