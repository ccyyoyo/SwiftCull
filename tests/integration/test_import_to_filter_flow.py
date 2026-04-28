from PIL import Image
from app.db.connection import get_connection, init_db
from app.db.photo_repository import PhotoRepository
from app.db.tag_repository import TagRepository
from app.core.import_service import ImportService
from app.core.tag_service import TagService
from app.core.filter_service import FilterService

def _make_jpeg(path):
    Image.new("RGB", (100, 80)).save(str(path), "JPEG")

def test_full_import_tag_filter_flow(tmp_path):
    (tmp_path / "sub").mkdir()
    _make_jpeg(tmp_path / "a.jpg")
    _make_jpeg(tmp_path / "b.jpg")
    _make_jpeg(tmp_path / "sub" / "c.jpg")

    conn = get_connection(str(tmp_path / "project.db"))
    init_db(conn)
    photo_repo = PhotoRepository(conn)
    tag_repo = TagRepository(conn)
    import_svc = ImportService()
    tag_svc = TagService(tag_repo)
    filter_svc = FilterService(photo_repo, tag_repo)

    paths = import_svc.scan_folder(str(tmp_path))
    assert len(paths) == 3
    ids = []
    for rel in paths:
        photo = import_svc.build_photo(str(tmp_path), rel)
        pid = photo_repo.insert(photo)
        ids.append(pid)

    tag_svc.set_status(ids[0], "pick")
    tag_svc.set_status(ids[1], "reject")
    tag_svc.set_color(ids[0], "red")

    picks = filter_svc.filter(statuses=["pick"])
    assert len(picks) == 1
    assert picks[0].id == ids[0]

    red_picks = filter_svc.filter(statuses=["pick"], colors=["red"])
    assert len(red_picks) == 1

    rejects = filter_svc.filter(statuses=["reject"])
    assert len(rejects) == 1

    untagged = filter_svc.filter(statuses=["untagged"])
    assert len(untagged) == 1
    assert untagged[0].id == ids[2]

    conn.close()
